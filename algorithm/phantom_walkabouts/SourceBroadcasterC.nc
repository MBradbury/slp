#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"
#include "NeighbourDetail.h"

#include "NormalMessage.h"
#include "AwayMessage.h"
#include "BeaconMessage.h"

#include <Timer.h>
#include <TinyError.h>
#include <stdio.h>

#include <assert.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, msg->landmark_distance + 1)
#define METRIC_RCV_BEACON(msg) METRIC_RCV(Beacon, source_addr, BOTTOM, BOTTOM, BOTTOM)

uint16_t message_no = 1;

typedef struct
{
	int16_t distance;
} distance_container_t;

void distance_update(distance_container_t* find, distance_container_t const* given)
{
	find->distance = minbot(find->distance, given->distance);
}

void distance_print(char* name, size_t i, am_addr_t address, distance_container_t const* contents)
{
	simdbg_clear(name, "[%u] => addr=%u / dist=%d",
		i, address, contents->distance);
}

DEFINE_NEIGHBOUR_DETAIL(distance_container_t, distance, distance_update, distance_print, SLP_MAX_1_HOP_NEIGHBOURHOOD);

#define UPDATE_NEIGHBOURS(rcvd, source_addr, name) \
{ \
	const distance_container_t dist = { rcvd->name }; \
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

	//typedef enum
	//{
	//	UnknownSet = 0, CloserSet = (1 << 0), FurtherSet = (1 << 1)
	//} SetType;

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

	distance_neighbours_t neighbours;

	bool busy = FALSE;
	message_t packet;

	uint32_t extra_to_send = 0;

	am_addr_t se[2]={0,0}; 
	am_addr_t ws[2]={0,0}; 
	am_addr_t nw[2]={0,0}; 
	am_addr_t ne[2]={0,0};

	//uint32_t se = 0, ws =0, nw = 0, ne =0;

	typedef enum
	{
		nw_dir, ne_dir, ws_dir, se_dir
	} SetType;

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
		uint32_t possible_set;
		uint32_t i;
		const uint16_t rnd = call Random.rand16()%4;

		if (rnd == 0)	return nw_dir;
		else if(rnd == 1)	return ne_dir;
		else if (rnd == 2)	return ws_dir;
		else	return se_dir;

	}

	am_addr_t random_walk_target(SetType set, const am_addr_t* to_ignore, size_t to_ignore_length)
	{
		am_addr_t chosen_address;
		uint32_t i;

		distance_neighbours_t local_neighbours;
		init_distance_neighbours(&local_neighbours);

		// If we don't know our sink distance then we cannot work
		// out which neighbour is in closer or further.
		if (landmark_distance != BOTTOM)
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

				//simdbgverbose("stdout", "[%u]: further_or_closer_set=%d, dist=%d neighbour.dist=%d \n",
				//  neighbour->address, further_or_closer_set, landmark_distance, neighbour->contents.distance);

				insert_distance_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
			}
		}

		if (local_neighbours.size == 0)
		{
			//simdbgverbose("stdout", "No local neighbours to choose so broadcasting. (my-dist=%d, my-neighbours-size=%u)\n",
			//	landmark_distance, neighbours.size);

			chosen_address = AM_BROADCAST_ADDR;
		}
		else
		{
			const uint16_t rnd = call Random.rand16();
			const uint16_t neighbour_index = rnd % 2;

			for(i = 0; i != neighbours.size; ++i)
			{
			distance_neighbour_detail_t const* const neighbour = &neighbours.data[i];

			if (landmark_distance < neighbour->contents.distance &&  neighbour->address < TOS_NODE_ID-1)
			{
				nw[0] = neighbour->address;
				ne[0] = neighbour->address;
			}
			else if (landmark_distance < neighbour->contents.distance && TOS_NODE_ID == neighbour->address+1)
			{
				nw[1] = neighbour->address;
				ws[0] = neighbour->address;
			}
			else if(landmark_distance > neighbour->contents.distance && neighbour->address > TOS_NODE_ID+1)
			{
				ws[1] =neighbour->address;
				se[0] = neighbour->address;
			}
			else if (landmark_distance > neighbour->contents.distance && neighbour->address == TOS_NODE_ID+1)
			{
				se[1]=neighbour->address;
				ne[1] =neighbour->address;
			}
			else
				 simdbgverbose("stdout","error here!TOS_NODE_ID= %u, neighbour address= %u\n",TOS_NODE_ID, neighbour->address);
			}
			// Choose a neighbour with equal probabilities.

			if (set == nw_dir) chosen_address = nw[neighbour_index];
			else if (set == ne_dir) chosen_address = ne[neighbour_index];
			else if (set == ws_dir) chosen_address = ws[neighbour_index];
			else if (set == se_dir) chosen_address = se[neighbour_index];
			else	simdbgverbose("stdout","error...\n");

			//const distance_neighbour_detail_t* const neighbour = &local_neighbours.data[neighbour_index];

			//chosen_address = neighbour->address;

#ifdef SLP_VERBOSE_DEBUG
			//print_distance_neighbours("stdout", &local_neighbours);
#endif

			//simdbgverbose("stdout", "Chosen %u at index %u (rnd=%u) out of %u neighbours (their-dist=%d my-dist=%d)\n",
			//	chosen_address, neighbour_index, rnd, local_neighbours.size,
			//	neighbour->contents.distance, landmark_distance);
		}

		simdbgverbose("stdout","chosen_address:%u\n",chosen_address);

		simdbgverbose("stdout","nw:%u, %u\n",nw[0],nw[1]);
		simdbgverbose("stdout","ne:%u, %u\n",ne[0],ne[1]);
		simdbgverbose("stdout","ws:%u, %u\n",ws[0],ws[1]);
		simdbgverbose("stdout","se:%u, %u\n",se[0],se[1]);
		return chosen_address;
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
		//simdbgverbose("Boot", "%s: Application booted.\n", sim_time_string());

		init_distance_neighbours(&neighbours);

		if (TOS_NODE_ID == SINK_NODE_ID)
		{
			type = SinkNode;
			simdbg("Node-Change-Notification", "The node has become a Sink\n");

			//sink_distance = 0;
		}

		call RadioControl.start();
	}

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			//simdbgverbose("SourceBroadcasterC", "%s: RadioControl started.\n", sim_time_string());

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
		//simdbgverbose("SourceBroadcasterC", "%s: RadioControl stopped.\n", sim_time_string());
	}

	event void ObjectDetector.detect()
	{
		// The sink node cannot become a source node
		if (type != SinkNode)
		{
			simdbg_clear("Metric-SOURCE_CHANGE", "set,%u\n", TOS_NODE_ID);
			simdbg("Node-Change-Notification", "The node has become a Source\n");

			type = SourceNode;

			call BroadcastNormalTimer.startOneShot(get_source_period());
		}
	}

	event void ObjectDetector.stoppedDetecting()
	{
		if (type == SourceNode)
		{
			call BroadcastNormalTimer.stop();

			type = NormalNode;

			simdbg_clear("Metric-SOURCE_CHANGE", "unset,%u\n", TOS_NODE_ID);
			simdbg("Node-Change-Notification", "The node has become a Normal\n");
		}
	}


	event void BroadcastNormalTimer.fired()
	{
		NormalMessage message;
		am_addr_t target;

		const uint32_t source_period = get_source_period();

		//simdbgverbose("SourceBroadcasterC", "%s: BroadcastNormalTimer fired.\n", sim_time_string());

#ifdef SLP_VERBOSE_DEBUG
		//print_distance_neighbours("stdout", &neighbours);
#endif

		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;
		message.landmark_distance_of_sender = landmark_distance;

		message.further_or_closer_set = random_walk_direction();

		target = random_walk_target(message.further_or_closer_set, NULL, 0);

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

		call BroadcastNormalTimer.startOneShot(source_period);
	}

	event void AwaySenderTimer.fired()
	{
		AwayMessage message;

		landmark_distance = 0;

		//simdbgverbose("SourceBroadcasterC", "%s: AwaySenderTimer fired.\n", sim_time_string());

		message.sequence_number = call AwaySeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.landmark_distance = landmark_distance;

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

		//simdbgverbose("SourceBroadcasterC", "%s: BeaconSenderTimer fired.\n", sim_time_string());

		message.landmark_distance_of_sender = landmark_distance;

		call Packet.clear(&packet);

		send_Beacon_message(&message, AM_BROADCAST_ADDR);
	}

	void process_normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_LANDMARK_DISTANCE(rcvd, landmark_distance_of_sender);
		
		UPDATE_NEIGHBOURS(rcvd, source_addr, landmark_distance_of_sender);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;
			forwarding_message.landmark_distance_of_sender = landmark_distance;

			if (rcvd->source_distance + 1 < RANDOM_WALK_HOPS && !rcvd->broadcast && TOS_NODE_ID != LANDMARK_NODE_ID)
			{
				am_addr_t target;

				// Get a target, ignoring the node that sent us this message
				target = random_walk_target(forwarding_message.further_or_closer_set, &source_addr, 1);

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
				if (!rcvd->broadcast && (rcvd->source_distance + 1 == RANDOM_WALK_HOPS || TOS_NODE_ID == LANDMARK_NODE_ID))
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
		UPDATE_NEIGHBOURS(rcvd, source_addr, landmark_distance);

		UPDATE_LANDMARK_DISTANCE(rcvd, landmark_distance);

		if (call AwaySeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			call AwaySeqNos.update(rcvd->source_id, rcvd->sequence_number);
			
			METRIC_RCV_AWAY(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.landmark_distance += 1;

			call Packet.clear(&packet);
			
			extra_to_send = 1;
			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);

			call BeaconSenderTimer.startOneShot(beacon_send_wait());
		}

#ifdef SLP_VERBOSE_DEBUG
		print_distance_neighbours("stdout", &neighbours);
#endif
	}

	RECEIVE_MESSAGE_BEGIN(Away, Receive)
		case NormalNode:
		case SourceNode:
		case SinkNode: x_receive_Away(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Away)


	void x_receieve_Beacon(message_t* msg, const BeaconMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(rcvd, source_addr, landmark_distance_of_sender);

		UPDATE_LANDMARK_DISTANCE(rcvd, landmark_distance_of_sender);

		METRIC_RCV_BEACON(rcvd);
	}

	RECEIVE_MESSAGE_BEGIN(Beacon, Receive)
		case NormalNode:
		case SourceNode:
		case SinkNode: x_receieve_Beacon(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Beacon)
}
