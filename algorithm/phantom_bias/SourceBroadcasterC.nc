#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"
#include "NeighbourDetail.h"

#include "NormalMessage.h"
#include "AwayMessage.h"
#include "BeaconMessage.h"

#include <Timer.h>
#include <TinyError.h>

#include <assert.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, msg->landmark_distance + 1)
#define METRIC_RCV_BEACON(msg) METRIC_RCV(Beacon, source_addr, BOTTOM, BOTTOM, BOTTOM)

typedef struct
{
	int16_t distance;
} distance_container_t;

void distance_update(distance_container_t* find, distance_container_t const* given)
{
	find->distance = minbot(find->distance, given->distance);
}

void distance_print(const char* name, size_t i, am_addr_t address, distance_container_t const* contents)
{
	simdbg_clear(name, "[%u] => addr=%u / dist=%d",
		i, address, contents->distance);
}

DEFINE_NEIGHBOUR_DETAIL(distance_container_t, distance, distance_update, distance_print, SLP_MAX_1_HOP_NEIGHBOURHOOD);


#define UPDATE_NEIGHBOURS(rcvd, source_addr, name) \
{ \
	const distance_container_t dist =  {rcvd->name}; \
	insert_distance_neighbour(&neighbours, source_addr, &dist); \
}

#define UPDATE_LANDMARK_DISTANCE(rcvd, name) \
{ \
	if (rcvd->name != BOTTOM) \
	{ \
		landmark_distance = minbot(landmark_distance, rcvd->name + 1); \
	} \
}

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;

	uses interface Timer<TMilli> as BroadcastNormalTimer;
	uses interface Timer<TMilli> as AwaySenderTimer;
	uses interface Timer<TMilli> as BeaconSenderTimer;

	uses interface Packet;
	uses interface AMPacket;

	uses interface SplitControl as RadioControl;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;
	uses interface Receive as NormalSnoop;

	uses interface AMSend as AwaySend;
	uses interface Receive as AwayReceive;

	uses interface AMSend as BeaconSend;
	uses interface Receive as BeaconReceive;

	uses interface SourcePeriodModel;
	uses interface ObjectDetector;

	uses interface SequenceNumbers as NormalSeqNos;
	uses interface SequenceNumbers as AwaySeqNos;
	 
	uses interface Random;
}

implementation 
{
	typedef enum
	{
		SourceNode, SinkNode, NormalNode
	} NodeType;

	NodeType type = NormalNode;

	typedef enum
	{
		UnknownSet = 0, CloserSet = (1 << 0), FurtherSet = (1 << 1)
	} SetType;

	typedef struct
	{
		int16_t address;
		int16_t neighbour_size;
	}neighbour_info;
	neighbour_info node_neighbours[SLP_MAX_1_HOP_NEIGHBOURHOOD]={{BOTTOM,BOTTOM},{BOTTOM,BOTTOM},{BOTTOM,BOTTOM},{BOTTOM,BOTTOM}};

	typedef struct
	{
		int16_t address;
		int16_t neighbour_size;
	}bias_neighbour;
	bias_neighbour bias_neighbours[2]={{BOTTOM,BOTTOM},{BOTTOM,BOTTOM}};

	typedef enum
	{
		UnknownMessageType, ShortRandomWalk, LongRandomWalk
	}MessageType;
	MessageType messagetype = UnknownMessageType;
	MessageType nextmessagetype = UnknownMessageType;

	const char* type_to_string()
	{
		switch (type)
		{
		case SourceNode:      return "SourceNode";
		case SinkNode:        return "SinkNode  ";
		case NormalNode:      return "NormalNode";
		default:              return "<unknown> ";
		}
	}

	int16_t landmark_distance = BOTTOM;

	int16_t srw_count = 0;	//short random walk count.
	int16_t lrw_count = 0;	//long random walk count.

	distance_neighbours_t neighbours;

	bool busy = FALSE;
	message_t packet;

	unsigned int extra_to_send = 0;

	uint32_t get_source_period()
	{
		assert(type == SourceNode);
		return call SourcePeriodModel.get();
	}

	// Produces a random float between 0 and 1
	float random_float()
	{
		// There appears to be problem with the 32 bit random number generator
		// in TinyOS that means it will not generate numbers in the full range
		// that a 32 bit integer can hold. So use the 16 bit value instead.
		// With the 16 bit integer we get better float values to compared to the
		// fake source probability.
		// Ref: https://github.com/tinyos/tinyos-main/issues/248
		const uint16_t rnd = call Random.rand16();

		return ((float)rnd) / UINT16_MAX;
	}

	SetType random_walk_direction()
	{
		uint32_t possible_sets = UnknownSet;

		// We want compare sink distance if we do not know our sink distance
		if (landmark_distance != BOTTOM)
		{
			uint32_t i;

			// Find nodes whose sink distance is less than or greater than
			// our sink distance.
			for (i = 0; i != neighbours.size; ++i)
			{
				distance_container_t const* const neighbour = &neighbours.data[i].contents;

				if (landmark_distance < neighbour->distance)
				{
					possible_sets |= FurtherSet;
				}
				else //if (landmark_distance >= neighbour->distance)
				{
					possible_sets |= CloserSet;
				}
			}
		}

		if (possible_sets == (FurtherSet | CloserSet) || (possible_sets & FurtherSet) != 0)
		{
			// Both directions or only FurtherSet possible, so  pick one FurtherSet
			return FurtherSet;
		}
		else if ((possible_sets & CloserSet) != 0)
		{
			return CloserSet;
		}
		else
		{
			// No known neighbours, so have a go at flooding.
			// Someone might get this message
			return UnknownSet;
		}
	}

	SetType neighbour_check(SetType further_or_closer_set, const am_addr_t* to_ignore, size_t to_ignore_length)
	{
		uint32_t i;

		distance_neighbours_t local_neighbours;
		init_distance_neighbours(&local_neighbours);

		// If we don't know our sink distance then we cannot work
		// out which neighbour is in closer or further.
		if (landmark_distance != BOTTOM && further_or_closer_set != UnknownSet)
		{
			for (i = 0; i != neighbours.size; ++i)
			{
				distance_neighbour_detail_t const* const neighbour = &neighbours.data[i];

				// Skip neighbours we have been asked to
				if (to_ignore != NULL)
				{
					size_t j;
					bool found = FALSE;
					for (j = 0; j != to_ignore_length; ++j)
					{
						if (to_ignore[j] == neighbour->address)
						{
							found = TRUE;
							break;
						}
					}
					if (found)
					{
						continue;
					}
				}

				if ((further_or_closer_set == FurtherSet && landmark_distance < neighbour->contents.distance) ||
					(further_or_closer_set == CloserSet && landmark_distance >= neighbour->contents.distance))
				{
					//local_neighbours.size++;
					insert_distance_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
				}
			}
		}
		if (further_or_closer_set == CloserSet && local_neighbours.size == 1)
		{
			simdbgverbose("stdout","need change to further!\n");
			return FurtherSet;
		}
		else if (local_neighbours.size == 0)
		{
			simdbgverbose("stdout","Need change Set.\n");
			return (further_or_closer_set == FurtherSet)? CloserSet: FurtherSet;
		}
		else
		{
			simdbgverbose("stdout", "<neighbour check>set type:%d, local neighbour size: %u\n",further_or_closer_set, local_neighbours.size);
			return further_or_closer_set;
		}
	}

	am_addr_t random_walk_target(SetType further_or_closer_set, const am_addr_t* to_ignore, size_t to_ignore_length)
	{
		am_addr_t chosen_address;
		uint32_t i;

		distance_neighbours_t local_neighbours;
		distance_neighbour_detail_t* neighbour_target;
		init_distance_neighbours(&local_neighbours);

		// If we don't know our sink distance then we cannot work
		// out which neighbour is in closer or further.
		if (landmark_distance != BOTTOM && further_or_closer_set != UnknownSet)
		{
			for (i = 0; i != neighbours.size; ++i)
			{
				distance_neighbour_detail_t const* const neighbour = &neighbours.data[i];

				// Skip neighbours we have been asked to
				if (to_ignore != NULL)
				{
					size_t j;
					bool found = FALSE;
					for (j = 0; j != to_ignore_length; ++j)
					{
						if (to_ignore[j] == neighbour->address)
						{
							found = TRUE;
							break;
						}
					}
					if (found)
					{
						continue;
					}
				}

				if ((further_or_closer_set == FurtherSet && landmark_distance < neighbour->contents.distance) ||
					(further_or_closer_set == CloserSet && landmark_distance >= neighbour->contents.distance))
				{
					insert_distance_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
				}
			}
		}
		simdbgverbose("stdout","--------------neighbours size is %d-----------------\n", local_neighbours.size);

		if (local_neighbours.size == 0)
		{
			simdbgverbose("stdout", "no neighbour is chosen! so broadcast!\n");
			chosen_address = AM_BROADCAST_ADDR;

		}

		else if (local_neighbours.size == 1)
		{
			chosen_address = local_neighbours.data[0].address;
			simdbgverbose("stdout", "neighbour size 1, so choose: %d\n", chosen_address);
		}

		else
		{
			int16_t m,j;

			for (m=0; m!=SLP_MAX_1_HOP_NEIGHBOURHOOD; ++m)
			{
				for(j=0; j!= 2; ++j)
				{
					if (node_neighbours[m].address == local_neighbours.data[j].address)
					{
						bias_neighbours[j].address = local_neighbours.data[j].address;
						bias_neighbours[j].neighbour_size = node_neighbours[m].neighbour_size;
						simdbgverbose("stdout", "neighbour[%d], address is %d, neighbour_size is %d\n",
							j, bias_neighbours[j].address, bias_neighbours[j].neighbour_size);
					}
				}
			}

			if (bias_neighbours[0].neighbour_size == bias_neighbours[1].neighbour_size)
			{
				// Choose a neighbour with equal probabilities.
				const uint16_t rnd = call Random.rand16();
				const uint16_t neighbour_index = rnd % local_neighbours.size;
				neighbour_target = &local_neighbours.data[neighbour_index];
				simdbgverbose("stdout","randomly pick one. Chosen:%d\n", neighbour_target->address);
			}
			else
			{
				neighbour_target = (bias_neighbours[0].neighbour_size < bias_neighbours[1].neighbour_size)? &local_neighbours.data[0]: &local_neighbours.data[1];
				simdbgverbose("stdout", "pick smaller one: %d\n", neighbour_target->address);
			} 

			chosen_address = neighbour_target->address;

#ifdef SLP_VERBOSE_DEBUG
			print_distance_neighbours("stdout", &local_neighbours);
#endif
		}

		return chosen_address;
	}

	int16_t short_long_sequence_random_walk(int16_t short_count, int16_t long_count)
	{
		int16_t rw;
		if (short_count != 0)
		{	
			rw = RANDOM_WALK_HOPS;
			srw_count -= 1;
		}
		else
		{
			rw = LONG_RANDOM_WALK_HOPS;
			lrw_count -= 1;
		}

		return rw;
	}

	int16_t long_short_sequence_random_walk(int16_t short_count, int16_t long_count)
	{
		int16_t rw;
		if (long_count != 0)
		{
			rw = LONG_RANDOM_WALK_HOPS;
			lrw_count -= 1;
		}
		else
		{
			rw = RANDOM_WALK_HOPS;
			srw_count -= 1;
		}

		return rw;
	}

	MessageType sl_next_message_type(int16_t srw, int16_t lrw)
	{
		MessageType sl_type;

		if (srw == 0 && lrw != 0)
			sl_type = LongRandomWalk;
		else
			sl_type = ShortRandomWalk;

		return sl_type;
	}

	MessageType ls_next_message_type(int16_t srw, int16_t lrw)
	{
		MessageType ls_type;

		if (lrw == 0 && srw != 0)
			ls_type = ShortRandomWalk;
		else
			ls_type = LongRandomWalk;

		return ls_type;
	}

	uint32_t beacon_send_wait()
	{
		return 75U + (uint32_t)(50U * random_float());
	}

	USE_MESSAGE(Normal);
	USE_MESSAGE(Away);
	USE_MESSAGE(Beacon);

	event void Boot.booted()
	{
		simdbgverbose("Boot", "%s: Application booted.\n", sim_time_string());

		init_distance_neighbours(&neighbours);

		if (TOS_NODE_ID == SINK_NODE_ID)
		{
			type = SinkNode;
			simdbg("Node-Change-Notification", "The node has become a Sink\n");
		}

		call RadioControl.start();
	}

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			simdbgverbose("SourceBroadcasterC", "%s: RadioControl started.\n", sim_time_string());

			call ObjectDetector.start();

			if (TOS_NODE_ID == LANDMARK_NODE_ID)
			{
				call AwaySenderTimer.startOneShot(1 * 1000); // One second
			}
		}
		else
		{
			simdbgerror("SourceBroadcasterC", "%s: RadioControl failed to start, retrying.\n", sim_time_string());

			call RadioControl.start();
		}
	}

	event void RadioControl.stopDone(error_t err)
	{
		simdbgverbose("SourceBroadcasterC", "%s: RadioControl stopped.\n", sim_time_string());
	}

	event void ObjectDetector.detect()
	{
		// The sink node cannot become a source node
		if (type != SinkNode)
		{
			simdbg("Metric-SOURCE_CHANGE", "set,%u\n", TOS_NODE_ID);
			simdbg("Node-Change-Notification", "The node has become a Source\n");

			type = SourceNode;

			call BroadcastNormalTimer.startOneShot(3 * 1000); // 3 seconds
		}
	}

	event void ObjectDetector.stoppedDetecting()
	{
		if (type == SourceNode)
		{
			call BroadcastNormalTimer.stop();

			type = NormalNode;

			simdbg("Metric-SOURCE_CHANGE", "unset,%u\n", TOS_NODE_ID);
			simdbg("Node-Change-Notification", "The node has become a Normal\n");
		}
	}

	event void BroadcastNormalTimer.fired()
	{
		NormalMessage message;
		am_addr_t target;

		const uint32_t source_period = get_source_period();

		simdbgverbose("SourceBroadcasterC", "%s: BroadcastNormalTimer fired.\n", sim_time_string());

#ifdef SLP_VERBOSE_DEBUG
		//print_distance_neighbours("stdout", &neighbours);
#endif

		if (srw_count == 0 && lrw_count == 0)
		{
			srw_count = SHORT_COUNT;
			lrw_count = LONG_COUNT;
		}

		#if defined(SHORT_LONG_SEQUENCE)
		{
			message.random_walk_hops = short_long_sequence_random_walk(srw_count, lrw_count);
			nextmessagetype = sl_next_message_type(srw_count, lrw_count);
		}
		#else
		{
			message.random_walk_hops = long_short_sequence_random_walk(srw_count, lrw_count);
			nextmessagetype = ls_next_message_type(srw_count, lrw_count);
		}
		#endif
		//simdbgverbose("stdout","random walk length:%d\n", message.random_walk_hops);
		messagetype = (message.random_walk_hops == RANDOM_WALK_HOPS)? ShortRandomWalk : LongRandomWalk;

		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;
		message.landmark_distance_of_sender = landmark_distance;

		message.neighbour_size = neighbours.size;
		message.node_id = TOS_NODE_ID;

		message.further_or_closer_set = random_walk_direction();	//choose further or closer.

		target = random_walk_target(message.further_or_closer_set, NULL, 0);
		simdbgverbose("stdout","----------------------------new message-----------------------------------------\n");

		// If we don't know who our neighbours are, then we
		// cannot unicast to one of them.
		if (target != AM_BROADCAST_ADDR)
		{
			message.broadcast = (target == AM_BROADCAST_ADDR);

			//simdbgverbose("stdout", "%s: Forwarding normal from source to target = %u in direction %u\n",
			//	sim_time_string(), target, message.further_or_closer_set);

			call Packet.clear(&packet);

			if (send_Normal_message(&message, target))
			{
				call NormalSeqNos.increment(TOS_NODE_ID);
			}
		}
		else
		{
			simdbg_clear("Metric-SOURCE_DROPPED", SIM_TIME_SPEC ",%u," SEQUENCE_NUMBER_SPEC "\n",
				sim_time(), TOS_NODE_ID, message.sequence_number);
		}

		if (messagetype == LongRandomWalk && nextmessagetype == ShortRandomWalk)
		{
			call BroadcastNormalTimer.startOneShot(WAIT_BEFORE_SHORT_MS + source_period);
		}
		else
		{
			call BroadcastNormalTimer.startOneShot(source_period);
		}
	}

	event void AwaySenderTimer.fired()
	{
		AwayMessage message;

		landmark_distance = 0;

		simdbgverbose("SourceBroadcasterC", "%s: AwaySenderTimer fired.\n", sim_time_string());

		message.sequence_number = call AwaySeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.landmark_distance = landmark_distance;

		message.neighbour_size = neighbours.size;
		message.node_id = TOS_NODE_ID;

		call Packet.clear(&packet);

		extra_to_send = 2;
		if (send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			call AwaySeqNos.increment(TOS_NODE_ID);
		}

		//simdbgverbose("stdout", "Away sent\n");
	}

	event void BeaconSenderTimer.fired()
	{
		BeaconMessage message;

		simdbgverbose("SourceBroadcasterC", "%s: BeaconSenderTimer fired.\n", sim_time_string());

		message.landmark_distance_of_sender = landmark_distance;

		message.neighbour_size = neighbours.size;
		message.node_id = TOS_NODE_ID;

		call Packet.clear(&packet);

		send_Beacon_message(&message, AM_BROADCAST_ADDR);
	}

	void process_normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		
		int16_t i;

		UPDATE_LANDMARK_DISTANCE(rcvd, landmark_distance_of_sender);
		
		UPDATE_NEIGHBOURS(rcvd, source_addr, landmark_distance_of_sender);

		for (i=0; i!=SLP_MAX_1_HOP_NEIGHBOURHOOD; i++)
		{
			if(node_neighbours[i].address == rcvd->node_id)
			{
				node_neighbours[i].neighbour_size = (node_neighbours[i].neighbour_size <= rcvd->neighbour_size)? 
				rcvd->neighbour_size: node_neighbours[i].neighbour_size;
				break;
			}
			else if (node_neighbours[i].address == BOTTOM)
			{
				node_neighbours[i].address = rcvd->node_id;
				node_neighbours[i].neighbour_size = rcvd->neighbour_size;
				break;
			}
			else
				continue;
		}
/*
		for (j=0;j!=SLP_MAX_1_HOP_NEIGHBOURHOOD;j++)
		{
			if(node_neighbours[j].address!=BOTTOM)
				simdbg("stdout","<After>neighbour address:%d, neighbour size:%d\n", node_neighbours[j].address, node_neighbours[j].neighbour_size);
		}
*/
		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;
			forwarding_message.landmark_distance_of_sender = landmark_distance;

			forwarding_message.neighbour_size = neighbours.size;
			forwarding_message.node_id = TOS_NODE_ID;

			if (rcvd->source_distance + 1 < rcvd->random_walk_hops && !rcvd->broadcast && TOS_NODE_ID != LANDMARK_NODE_ID)
			{
				am_addr_t target;

				// The previous node(s) were unable to choose a direction,
				// so lets try to work out the direction the message should go in.
/*
				if (forwarding_message.further_or_closer_set == UnknownSet)
				{
					const distance_neighbour_detail_t* neighbour_detail = find_distance_neighbour(&neighbours, source_addr);
					if (neighbour_detail != NULL)
					{
						forwarding_message.further_or_closer_set =
							neighbour_detail->contents.distance < landmark_distance ? FurtherSet : CloserSet;
					}
					else
					{
						forwarding_message.further_or_closer_set = random_walk_direction();
					}

					simdbgverbose("stdout", "%s: Unknown direction, setting to %d\n",
						sim_time_string(), forwarding_message.further_or_closer_set);
				}
*/
				// Get a target, ignoring the node that sent us this message

				forwarding_message.further_or_closer_set = neighbour_check(rcvd->further_or_closer_set, &source_addr, 1);//if chosen size is 0, choose the other set.
				
				target = random_walk_target(forwarding_message.further_or_closer_set, &source_addr, 1);
				simdbgverbose("stdout", "After target function, target is %d\n", target);

				forwarding_message.broadcast = (target == AM_BROADCAST_ADDR);

				// A node on the path away from, or towards the landmark node
				// doesn't have anyone to send to.
				// We do not want to broadcast here as it may lead the attacker towards the source.
				if (target == AM_BROADCAST_ADDR)
				{
					simdbg_clear("Metric-PATH_DROPPED", SIM_TIME_SPEC ",%u," SEQUENCE_NUMBER_SPEC ",%u\n",
						sim_time(), TOS_NODE_ID, rcvd->sequence_number, rcvd->source_distance);

					return;
				}

				//simdbgverbose("stdout", "%s: Forwarding normal from %u to target = %u\n",
				//	sim_time_string(), TOS_NODE_ID, target);

				call Packet.clear(&packet);

				send_Normal_message(&forwarding_message, target);
			}
			else
			{
				if (!rcvd->broadcast && (rcvd->source_distance + 1 == rcvd->random_walk_hops || TOS_NODE_ID == LANDMARK_NODE_ID))
				{
					simdbg_clear("Metric-PATH-END", SIM_TIME_SPEC ",%u,%u,%u," SEQUENCE_NUMBER_SPEC ",%u\n",
						sim_time(), TOS_NODE_ID, source_addr,
						rcvd->source_id, rcvd->sequence_number, rcvd->source_distance + 1);
				}

				// We want other nodes to continue broadcasting
				forwarding_message.broadcast = TRUE;

				call Packet.clear(&packet);

				send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
			}
		}
	}

	void Normal_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		process_normal(msg, rcvd, source_addr);
	}

	void Sink_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		// It is helpful to have the sink forward Normal messages onwards
		// Otherwise there is a chance the random walk would terminate at the sink and
		// not flood the network.
		process_normal(msg, rcvd, source_addr);
	}

	void Source_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{

		UPDATE_NEIGHBOURS(rcvd, source_addr, landmark_distance_of_sender);

		UPDATE_LANDMARK_DISTANCE(rcvd, landmark_distance_of_sender);
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SourceNode: Source_receieve_Normal(msg, rcvd, source_addr); break;
		case SinkNode: Sink_receieve_Normal(msg, rcvd, source_addr); break;
		case NormalNode: Normal_receieve_Normal(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)

	// If the sink snoops a normal message, we may as well just deliver it
	void Sink_snoop_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{

		UPDATE_NEIGHBOURS(rcvd, source_addr, landmark_distance_of_sender);

		UPDATE_LANDMARK_DISTANCE(rcvd, landmark_distance_of_sender);

		// TODO: Enable this when the sink can snoop and then correctly
		// respond to a message being received.
		/*if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			simdbgverbose("stdout", "%s: Received unseen Normal by snooping seqno=%u from %u (dsrc=%u).\n",
				sim_time_string(), rcvd->sequence_number, source_addr, rcvd->source_distance + 1);
		}*/
	}

	void x_snoop_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{

		UPDATE_NEIGHBOURS(rcvd, source_addr, landmark_distance_of_sender);

		UPDATE_LANDMARK_DISTANCE(rcvd, landmark_distance_of_sender);

		//simdbgverbose("stdout", "Snooped a normal from %u intended for %u (rcvd-dist=%d, my-dist=%d)\n",
		//  source_addr, call AMPacket.destination(msg), rcvd->landmark_distance_of_sender, landmark_distance);
	}

	// We need to snoop packets that may be unicasted,
	// so the attacker properly responds to them.
	RECEIVE_MESSAGE_BEGIN(Normal, Snoop)
		case SourceNode: x_snoop_Normal(msg, rcvd, source_addr); break;
		case SinkNode: Sink_snoop_Normal(msg, rcvd, source_addr); break;
		case NormalNode: x_snoop_Normal(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)

	void x_receive_Away(message_t* msg, const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		//int16_t ii;

		UPDATE_NEIGHBOURS(rcvd, source_addr, landmark_distance);
		UPDATE_LANDMARK_DISTANCE(rcvd, landmark_distance);
/*
		for (ii=0; ii!=SLP_MAX_1_HOP_NEIGHBOURHOOD; ii++)
		{
			if(node_neighbours[ii].address == rcvd->node_id)
			{
				node_neighbours[ii].neighbour_size = (node_neighbours[ii].neighbour_size <= rcvd->neighbour_size)? 
				rcvd->neighbour_size: node_neighbours[ii].neighbour_size;
				break;
			}
			else if (node_neighbours[ii].address == BOTTOM)
			{
				node_neighbours[ii].address = rcvd->node_id;
				node_neighbours[ii].neighbour_size = rcvd->neighbour_size;
				break;
			}
			else
				continue;
		}
*/
		if (call AwaySeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			call AwaySeqNos.update(rcvd->source_id, rcvd->sequence_number);
			
			METRIC_RCV_AWAY(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.landmark_distance += 1;

			forwarding_message.node_id = TOS_NODE_ID;
			forwarding_message.neighbour_size = neighbours.size;

			call Packet.clear(&packet);
			
			extra_to_send = 1;
			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);

			call BeaconSenderTimer.startOneShot(beacon_send_wait());
		}

#ifdef SLP_VERBOSE_DEBUG
		//print_distance_neighbours("stdout", &neighbours);
#endif
	}

	RECEIVE_MESSAGE_BEGIN(Away, Receive)
		case NormalNode:
		case SourceNode:
		case SinkNode: x_receive_Away(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Away)


	void x_receieve_Beacon(message_t* msg, const BeaconMessage* const rcvd, am_addr_t source_addr)
	{
		int16_t i;

		UPDATE_NEIGHBOURS(rcvd, source_addr, landmark_distance_of_sender);

		UPDATE_LANDMARK_DISTANCE(rcvd, landmark_distance_of_sender);

		METRIC_RCV_BEACON(rcvd);


		for (i=0; i!=SLP_MAX_1_HOP_NEIGHBOURHOOD; i++)
		{
			if(node_neighbours[i].address == rcvd->node_id)
			{
				node_neighbours[i].neighbour_size = (node_neighbours[i].neighbour_size <= rcvd->neighbour_size)? 
				rcvd->neighbour_size: node_neighbours[i].neighbour_size;
				break;
			}
			else if (node_neighbours[i].address == BOTTOM)
			{
				node_neighbours[i].address = rcvd->node_id;
				node_neighbours[i].neighbour_size = rcvd->neighbour_size;
				break;
			}
			else
				continue;
		}
	

	}

	RECEIVE_MESSAGE_BEGIN(Beacon, Receive)
		case NormalNode:
		case SourceNode:
		case SinkNode: x_receieve_Beacon(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Beacon)
}
