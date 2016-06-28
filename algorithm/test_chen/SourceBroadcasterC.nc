#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"
#include "NeighbourDetail.h"

#include "NormalMessage.h"
#include "AwayMessage.h"
#include "BeaconMessage.h"

#include <Timer.h>
#include <TinyError.h>
#include <math.h>
#include <unistd.h>

#include <assert.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, msg->landmark_distance + 1)
#define METRIC_RCV_BEACON(msg) METRIC_RCV(Beacon, source_addr, BOTTOM, BOTTOM, BOTTOM)

typedef struct
{
	uint16_t bottom_left_distance;
	uint16_t bottom_right_distance;
	uint16_t top_right_distance;
	uint16_t sink_distance;
} distance_container_t;

void distance_update(distance_container_t* find, distance_container_t const* given)
{
	find->bottom_left_distance = minbot(find->bottom_left_distance, given->bottom_left_distance);
	find->bottom_right_distance = minbot(find->bottom_right_distance, given->bottom_right_distance);
	find->top_right_distance = minbot(find->top_right_distance, given->top_right_distance);

	find->sink_distance = minbot(find->sink_distance, given->sink_distance);
}

void distance_print(const char* name, size_t i, am_addr_t address, distance_container_t const* contents)
{
	simdbg_clear(name, "[%u] => addr=%u / bl=%d, br=%d, tr=%d, sink_dist=%d",
		i, address, contents->bottom_left_distance, contents->bottom_right_distance, contents->top_right_distance, contents->sink_distance);
}

DEFINE_NEIGHBOUR_DETAIL(distance_container_t, distance, distance_update, distance_print, SLP_MAX_1_HOP_NEIGHBOURHOOD);

#define UPDATE_NEIGHBOURS_BL(rcvd, source_addr, name) \
{ \
	distance_container_t dist; \
	dist.bottom_left_distance = rcvd->name; \
	dist.bottom_right_distance = BOTTOM; \
	dist.top_right_distance = BOTTOM; \
	dist.sink_distance = BOTTOM; \
	insert_distance_neighbour(&neighbours, source_addr, &dist); \
}

#define UPDATE_NEIGHBOURS_BR(rcvd, source_addr, name) \
{ \
	distance_container_t dist; \
	dist.bottom_left_distance = BOTTOM; \
	dist.bottom_right_distance = rcvd->name; \
	dist.top_right_distance = BOTTOM; \
	dist.sink_distance = BOTTOM; \
	insert_distance_neighbour(&neighbours, source_addr, &dist); \
}

#define UPDATE_NEIGHBOURS_TR(rcvd, source_addr, name) \
{ \
	distance_container_t dist; \
	dist.bottom_left_distance = BOTTOM; \
	dist.top_right_distance = rcvd->name; \
	dist.bottom_right_distance = BOTTOM; \
	dist.sink_distance = BOTTOM; \
	insert_distance_neighbour(&neighbours, source_addr, &dist); \
}

#define UPDATE_NEIGHBOURS_SINK(rcvd, source_addr, name) \
{ \
	distance_container_t dist; \
	dist.sink_distance = rcvd->name;\
	dist.bottom_left_distance = BOTTOM; \
	dist.bottom_right_distance = BOTTOM; \
	dist.top_right_distance = BOTTOM; \
	insert_distance_neighbour(&neighbours, source_addr, &dist); \
}

#define UPDATE_LANDMARK_DISTANCE_BL(rcvd, name) \
{ \
	if (rcvd->name != BOTTOM) \
	{ \
		landmark_bottom_left_distance = minbot(landmark_bottom_left_distance, botinc(rcvd->name)); \
	} \
}

#define UPDATE_LANDMARK_DISTANCE_BR(rcvd, name) \
{ \
	if (rcvd->name != BOTTOM) \
	{ \
		landmark_bottom_right_distance = minbot(landmark_bottom_right_distance, botinc(rcvd->name)); \
	} \
}

#define UPDATE_LANDMARK_DISTANCE_TR(rcvd, name) \
{ \
	if (rcvd->name != BOTTOM) \
	{ \
		landmark_top_right_distance = minbot(landmark_top_right_distance, botinc(rcvd->name)); \
	} \
}

#define UPDATE_LANDMARK_DISTANCE_SINK(rcvd, name) \
{ \
	if (rcvd->name != BOTTOM) \
	{ \
		landmark_sink_distance = minbot(landmark_sink_distance, botinc(rcvd->name)); \
	} \
}

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;

	uses interface Timer<TMilli> as BroadcastNormalTimer;
	uses interface Timer<TMilli> as AwaySenderTimer;
	uses interface Timer<TMilli> as DelayBLSenderTimer;
	uses interface Timer<TMilli> as DelayBRSenderTimer;
	uses interface Timer<TMilli> as DelayTRSenderTimer;
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
		UnknownSet = 0, CloserSet = (1 << 0), FurtherSet = (1 << 1), CloserSideSet = (1 << 2), FurtherSideSet = (1 << 3)
	} SetType;

	typedef enum
	{
		UnknownLocation, Centre, Others 
	}SinkLocation;
	SinkLocation location = UnknownLocation;

	typedef enum
	{
		UnknownBias, H, V 
	}BiasedType;
	BiasedType biased = UnknownBias;

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

	uint16_t landmark_bottom_left_distance = BOTTOM;
	uint16_t landmark_bottom_right_distance = BOTTOM;
	uint16_t landmark_top_right_distance = BOTTOM;
	uint16_t landmark_sink_distance = BOTTOM;

	uint16_t sink_bl_dist = BOTTOM;		//sink-bottom_left distance.
	uint16_t sink_br_dist = BOTTOM;		//sink-bottom_right distance.
	uint16_t sink_tr_dist = BOTTOM;		//sink-top_right distance.

	uint16_t srw_count = 0;	//short random walk count.
	uint16_t lrw_count = 0;	//long random walk count.

	distance_neighbours_t neighbours;

	bool busy = FALSE;
	message_t packet;

	uint32_t extra_to_send = 0;

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
		uint16_t possible_sets = UnknownSet;

		uint32_t FurtherSet_neighbours = 0;
		uint32_t CloserSideSet_neighbours = 0;
		uint32_t CloserSet_neighbours = 0;
		uint32_t FurtherSideSet_neighbours = 0;

		//simdbg("stdout", "landmark_bottom_left_distance=%u, landmark_bottom_right_distance=%u", landmark_bottom_left_distance, landmark_bottom_right_distance);

		if (landmark_bottom_left_distance != BOTTOM && landmark_bottom_right_distance != BOTTOM)
		{
			uint32_t i;

			// Find nodes whose sink distance is less than or greater than
			// our sink distance.
			for (i = 0; i != neighbours.size; ++i)
			{
				distance_container_t const* const neighbour = &neighbours.data[i].contents;

				if (landmark_bottom_right_distance < neighbour->bottom_right_distance)
				{
					possible_sets |= FurtherSet;
					//FurtherSet_neighbours ++;
				}
				else //if (landmark_distance >= neighbour->distance)
				{
					possible_sets |= CloserSet;
					//CloserSet_neighbours ++;
				}
			}
		}

		//if (CloserSet_neighbours == 2)	possible_sets |= CloserSet;
		//if (FurtherSet_neighbours == 2)	possible_sets |= FurtherSet;

		if (possible_sets == (FurtherSet | CloserSet))
		{
			// Both directions possible, so randomly pick one of them
			const uint16_t rnd = call Random.rand16() % 2;
			if (rnd == 0)
			{
				return FurtherSet;
			}
			else
			{
				return CloserSet;
			}
		}
		else if ((possible_sets & FurtherSet) != 0)
		{
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

/*
		uint16_t FurtherSet_neighbours = 0;
		uint16_t CloserSideSet_neighbours = 0;
		uint16_t CloserSet_neighbours = 0;
		uint16_t FurtherSideSet_neighbours = 0;

		if (landmark_bottom_left_distance != BOTTOM && landmark_bottom_right_distance != BOTTOM)
		{
			uint32_t i;
			for (i = 0; i != neighbours.size; ++i)
			{
				distance_container_t const* const neighbour = &neighbours.data[i].contents;

				if (landmark_bottom_left_distance < neighbour->bottom_left_distance && landmark_bottom_right_distance <  neighbour->bottom_right_distance)
				{
					FurtherSet_neighbours ++;
					FurtherSideSet_neighbours ++;					
				}
				else if (landmark_bottom_left_distance > neighbour->bottom_left_distance && landmark_bottom_right_distance < neighbour->bottom_right_distance)
				{
					CloserSideSet_neighbours ++;
					FurtherSet_neighbours ++;
				}
				else if (landmark_bottom_left_distance > neighbour->bottom_left_distance && landmark_bottom_right_distance >  neighbour->bottom_right_distance)
				{
					CloserSet_neighbours ++;
					CloserSideSet_neighbours ++;					
				}
				else //(landmark_bottom_left_distance < neighbour->bottom_left_distance && landmark_bottom_right_distance > neighbour->bottom_right_distance)
				{
					CloserSet_neighbours ++;
					FurtherSideSet_neighbours ++;
				}
			}
			//simdbg("stdout", "landmark_bottom_left_distance=%u, landmark_bottom_right_distance=%u", landmark_bottom_left_distance, landmark_bottom_right_distance);
		}

		if (FurtherSideSet_neighbours == 2)
		{
			possible_sets |= FurtherSideSet;
		}
		if (CloserSideSet_neighbours == 2)
		{
			possible_sets |= CloserSideSet;
		}
		if (FurtherSet_neighbours == 2)		
		{
			possible_sets |= FurtherSet;
		}
		if (CloserSet_neighbours == 2)	
		{
			possible_sets |= CloserSet;
		}

		//simdbg("stdout", "possible_sets=%u  ", possible_sets);

		if (possible_sets == (CloserSet | FurtherSet | CloserSideSet | FurtherSideSet))
		{	
			uint16_t rnd = call Random.rand16() % 4;
			if(rnd == 0)			return CloserSet;
			else if (rnd == 1)		return FurtherSet;
			else if (rnd == 2)		return CloserSideSet;
			else					return FurtherSideSet;
		}

		else if (possible_sets == (CloserSet|CloserSideSet))
		{
			uint16_t rnd = call Random.rand16() % 2;
			if(rnd == 0)			return CloserSet;
			else					return CloserSideSet;
		}

		else if (possible_sets == (CloserSet|FurtherSideSet))
		{
			uint16_t rnd = call Random.rand16() % 2;
			if(rnd == 0)			return CloserSet;
			else					return FurtherSideSet;
		}

		else if (possible_sets == (FurtherSet|FurtherSideSet))
		{
			uint16_t rnd = call Random.rand16() % 2;
			if(rnd == 0)			return FurtherSet;
			else					return FurtherSideSet;
		}

		else if (possible_sets == (FurtherSet|CloserSideSet))
		{
			uint16_t rnd = call Random.rand16() % 2;
			if(rnd == 0)			return FurtherSet;
			else					return CloserSideSet;
		}

		else if ((possible_sets & CloserSet) != 0)
		{
			return CloserSet;
		}
		else if ((possible_sets & FurtherSet) != 0)
		{
			return FurtherSet;
		}

		else if ((possible_sets & CloserSideSet) != 0)
		{
			return CloserSideSet;
		}
		else if ((possible_sets & FurtherSideSet) != 0)
		{
			return FurtherSideSet;
		}
		else
		{
			return UnknownSet;
		}
*/
	}

	am_addr_t random_walk_target(SetType further_or_closer_set, const am_addr_t* to_ignore, size_t to_ignore_length)
	{
		am_addr_t chosen_address;
		uint32_t i;

		distance_neighbours_t local_neighbours;
		init_distance_neighbours(&local_neighbours);

		// If we don't know our sink distance then we cannot work
		// out which neighbour is in closer or further.
		if (landmark_bottom_left_distance != BOTTOM && further_or_closer_set != UnknownSet)
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
				if ((further_or_closer_set == FurtherSet && landmark_bottom_right_distance < neighbour->contents.bottom_right_distance) ||
					(further_or_closer_set == CloserSet && landmark_bottom_right_distance >= neighbour->contents.bottom_right_distance))
				{
					insert_distance_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
				}
/*
				if ((further_or_closer_set == FurtherSet && landmark_bottom_right_distance < neighbour->contents.bottom_right_distance) ||
					(further_or_closer_set == CloserSet && landmark_bottom_right_distance >= neighbour->contents.bottom_right_distance) ||
					(further_or_closer_set == FurtherSideSet && landmark_bottom_left_distance < neighbour->contents.bottom_left_distance) ||
					(further_or_closer_set == CloserSideSet && landmark_bottom_left_distance >= neighbour->contents.bottom_left_distance))
				{
					insert_distance_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
				}
*/				
			}
		}
		else
		{
			chosen_address = AM_BROADCAST_ADDR;
		}

		if (local_neighbours.size == 0)
		{
			simdbgverbose("stdout", "No local neighbours to choose so broadcasting. (my-dist=%d, my-neighbours-size=%u)\n",
				landmark_distance, neighbours.size);

			chosen_address = AM_BROADCAST_ADDR;
		}
		else
		{
			// Choose a neighbour with equal probabilities.
			const uint16_t rnd = call Random.rand16();
			const uint16_t neighbour_index = rnd % local_neighbours.size;
			const distance_neighbour_detail_t* const neighbour = &local_neighbours.data[neighbour_index];

			chosen_address = neighbour->address;

#ifdef SLP_VERBOSE_DEBUG
			print_distance_neighbours("stdout", &local_neighbours);
#endif

			simdbgverbose("stdout", "Chosen %u at index %u (rnd=%u) out of %u neighbours (their-dist=%d my-dist=%d)\n",
				chosen_address, neighbour_index, rnd, local_neighbours.size,
				neighbour->contents.distance, landmark_distance);
		}

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
		simdbgverbose("Boot", "%s: Application booted.\n", sim_time_string());

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
			simdbgverbose("SourceBroadcasterC", "%s: RadioControl started.\n", sim_time_string());

			call ObjectDetector.start();

			if (TOS_NODE_ID == SINK_NODE_ID)
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
			simdbg_clear("Metric-SOURCE_CHANGE", "set,%u\n", TOS_NODE_ID);
			simdbg("Node-Change-Notification", "The node has become a Source\n");

			type = SourceNode;

			call BroadcastNormalTimer.startOneShot(6 * 1000);
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

	event void DelayBLSenderTimer.fired()
	{
		AwayMessage message;

		landmark_bottom_left_distance = 0;
		message.landmark_location = BOTTOMLEFT;
		message.sequence_number = call AwaySeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.landmark_distance = 0;
		message.sink_bl_dist = sink_bl_dist;

		call Packet.clear(&packet);

		extra_to_send = 2;
		if (send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			call AwaySeqNos.increment(TOS_NODE_ID);
		}
	}

	event void DelayBRSenderTimer.fired()
	{
		AwayMessage message;

		landmark_bottom_right_distance = 0;
		message.landmark_location = BOTTOMRIGHT;
		message.sequence_number = call AwaySeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.landmark_distance = 0;
		message.sink_br_dist = sink_br_dist;

		call Packet.clear(&packet);

		extra_to_send = 2;
		if (send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			call AwaySeqNos.increment(TOS_NODE_ID);
		}
	}

	event void DelayTRSenderTimer.fired()
	{
		AwayMessage message;

		landmark_top_right_distance = 0;
		message.landmark_location = TOPRIGHT;
		message.sequence_number = call AwaySeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.landmark_distance = 0;
		message.sink_tr_dist = sink_tr_dist;

		call Packet.clear(&packet);

		extra_to_send = 2;
		if (send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			call AwaySeqNos.increment(TOS_NODE_ID);
		}
	}


	event void BroadcastNormalTimer.fired()
	{
		NormalMessage message;
		am_addr_t target;

		const uint32_t source_period = get_source_period();

		simdbgverbose("SourceBroadcasterC", "%s: BroadcastNormalTimer fired.\n", sim_time_string());

#ifdef SLP_VERBOSE_DEBUG
		print_distance_neighbours("stdout", &neighbours);
#endif
		
		//simdbg("stdout", "BroadcastNormalTimer fired.\n");

		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;
		
		message.landmark_distance_of_bottom_left_sender = landmark_bottom_left_distance;
		message.landmark_distance_of_bottom_right_sender = landmark_bottom_right_distance;
		message.landmark_distance_of_top_right_sender = landmark_top_right_distance;
		message.landmark_distance_of_sink_sender = landmark_sink_distance;

		message.further_or_closer_set = random_walk_direction();

		//simdbg("stdout","choose direction:%u\n",message.further_or_closer_set);

		target = random_walk_target(message.further_or_closer_set, NULL, 0);

		// If we don't know who our neighbours are, then we
		// cannot unicast to one of them.
		if (target != AM_BROADCAST_ADDR)
		{
			message.broadcast = (target == AM_BROADCAST_ADDR);

			simdbgverbose("stdout", "%s: Forwarding normal from source to target = %u in direction %u\n",
				sim_time_string(), target, message.further_or_closer_set);

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

		if (TOS_NODE_ID == SINK_NODE_ID)
		{
			landmark_sink_distance = 0;
			message.landmark_location = SINK;
		}
		else
		{
			simdbgerror("stdout", "Error!\n");
		}

		message.sequence_number = call AwaySeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.landmark_distance = 0;

		call Packet.clear(&packet);

		extra_to_send = 2;
		if (send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			call AwaySeqNos.increment(TOS_NODE_ID);
		}

	}

	event void BeaconSenderTimer.fired()
	{
		BeaconMessage message;

		simdbgverbose("SourceBroadcasterC", "%s: BeaconSenderTimer fired.\n", sim_time_string());

		message.landmark_distance_of_bottom_left_sender = landmark_bottom_left_distance;
		message.landmark_distance_of_bottom_right_sender = landmark_bottom_right_distance;
		message.landmark_distance_of_top_right_sender = landmark_top_right_distance;
		message.landmark_distance_of_sink_sender = landmark_sink_distance;

		call Packet.clear(&packet);

		send_Beacon_message(&message, AM_BROADCAST_ADDR);
	}

	void process_normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_LANDMARK_DISTANCE_BL(rcvd, landmark_distance_of_bottom_left_sender);
		UPDATE_LANDMARK_DISTANCE_BR(rcvd, landmark_distance_of_bottom_right_sender);
		UPDATE_LANDMARK_DISTANCE_TR(rcvd, landmark_distance_of_top_right_sender);
		UPDATE_LANDMARK_DISTANCE_SINK(rcvd, landmark_distance_of_sink_sender);
		
		UPDATE_NEIGHBOURS_BL(rcvd, source_addr, landmark_distance_of_bottom_left_sender);
		UPDATE_NEIGHBOURS_BR(rcvd, source_addr, landmark_distance_of_bottom_right_sender);
		UPDATE_NEIGHBOURS_TR(rcvd, source_addr, landmark_distance_of_top_right_sender);		
		UPDATE_NEIGHBOURS_SINK(rcvd, source_addr, landmark_distance_of_sink_sender);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;

			forwarding_message.landmark_distance_of_bottom_left_sender = landmark_bottom_left_distance;
			forwarding_message.landmark_distance_of_bottom_right_sender = landmark_bottom_right_distance;
			forwarding_message.landmark_distance_of_top_right_sender = landmark_top_right_distance;
			forwarding_message.landmark_distance_of_sink_sender = landmark_sink_distance;

			if (rcvd->source_distance + 1 < RANDOM_WALK_HOPS && !rcvd->broadcast && TOS_NODE_ID != LANDMARK_NODE_ID)
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
				target = random_walk_target(forwarding_message.further_or_closer_set, &source_addr, 1);

				forwarding_message.broadcast = (target == AM_BROADCAST_ADDR);

				// A node on the path away from, or towards the landmark node
				// doesn't have anyone to send to.
				// We do not want to broadcast here as it may lead the attacker towards the source.
				if (target == AM_BROADCAST_ADDR)
				{
					simdbg_clear("Metric-PATH_DROPPED", SIM_TIME_SPEC ",%u," SEQUENCE_NUMBER_SPEC ",%u\n",
						sim_time(), TOS_NODE_ID, rcvd->sequence_number, rcvd->source_distance);

					//return;
				}

				simdbgverbose("stdout", "%s: Forwarding normal from %u to target = %u\n",
					sim_time_string(), TOS_NODE_ID, target);

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
		UPDATE_NEIGHBOURS_BL(rcvd, source_addr, landmark_distance_of_bottom_left_sender);
		UPDATE_NEIGHBOURS_BR(rcvd, source_addr, landmark_distance_of_bottom_right_sender);
		UPDATE_NEIGHBOURS_TR(rcvd, source_addr, landmark_distance_of_top_right_sender);
		UPDATE_NEIGHBOURS_SINK(rcvd, source_addr, landmark_distance_of_sink_sender);

		UPDATE_LANDMARK_DISTANCE_BL(rcvd, landmark_distance_of_bottom_left_sender);
		UPDATE_LANDMARK_DISTANCE_BR(rcvd, landmark_distance_of_bottom_right_sender);
		UPDATE_LANDMARK_DISTANCE_TR(rcvd, landmark_distance_of_top_right_sender);
		UPDATE_LANDMARK_DISTANCE_SINK(rcvd, landmark_distance_of_sink_sender);
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SourceNode: Source_receieve_Normal(msg, rcvd, source_addr); break;
		case SinkNode: Sink_receieve_Normal(msg, rcvd, source_addr); break;
		case NormalNode: Normal_receieve_Normal(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)

	// If the sink snoops a normal message, we may as well just deliver it
	void Sink_snoop_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS_BL(rcvd, source_addr, landmark_distance_of_bottom_left_sender);
		UPDATE_NEIGHBOURS_BR(rcvd, source_addr, landmark_distance_of_bottom_right_sender);
		UPDATE_NEIGHBOURS_TR(rcvd, source_addr, landmark_distance_of_top_right_sender);
		UPDATE_NEIGHBOURS_SINK(rcvd, source_addr, landmark_distance_of_sink_sender);

		UPDATE_LANDMARK_DISTANCE_BL(rcvd, landmark_distance_of_bottom_left_sender);
		UPDATE_LANDMARK_DISTANCE_BR(rcvd, landmark_distance_of_bottom_right_sender);
		UPDATE_LANDMARK_DISTANCE_TR(rcvd, landmark_distance_of_top_right_sender);
		UPDATE_LANDMARK_DISTANCE_SINK(rcvd, landmark_distance_of_sink_sender);

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
		UPDATE_NEIGHBOURS_BL(rcvd, source_addr, landmark_distance_of_bottom_left_sender);
		UPDATE_NEIGHBOURS_BR(rcvd, source_addr, landmark_distance_of_bottom_right_sender);
		UPDATE_NEIGHBOURS_TR(rcvd, source_addr, landmark_distance_of_top_right_sender);
		UPDATE_NEIGHBOURS_SINK(rcvd, source_addr, landmark_distance_of_sink_sender);

		UPDATE_LANDMARK_DISTANCE_BL(rcvd, landmark_distance_of_bottom_left_sender);
		UPDATE_LANDMARK_DISTANCE_BR(rcvd, landmark_distance_of_bottom_right_sender);
		UPDATE_LANDMARK_DISTANCE_TR(rcvd, landmark_distance_of_top_right_sender);
		UPDATE_LANDMARK_DISTANCE_SINK(rcvd, landmark_distance_of_sink_sender);

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
		if (rcvd->landmark_location == BOTTOMLEFT)
		{
			sink_bl_dist = rcvd->sink_bl_dist;
			UPDATE_NEIGHBOURS_BL(rcvd, source_addr, landmark_distance);
			UPDATE_LANDMARK_DISTANCE_BL(rcvd, landmark_distance);
		}
		if (rcvd->landmark_location == BOTTOMRIGHT)
		{
			sink_br_dist = rcvd->sink_br_dist;
			UPDATE_NEIGHBOURS_BR(rcvd, source_addr, landmark_distance);
			UPDATE_LANDMARK_DISTANCE_BR(rcvd, landmark_distance);
		}
		if (rcvd->landmark_location == SINK)
		{
			UPDATE_NEIGHBOURS_SINK(rcvd, source_addr, landmark_distance);
			UPDATE_LANDMARK_DISTANCE_SINK(rcvd, landmark_distance);
		}
		if (rcvd->landmark_location == TOPRIGHT)
		{
			sink_tr_dist = rcvd->sink_tr_dist;
			UPDATE_NEIGHBOURS_TR(rcvd, source_addr, landmark_distance);
			UPDATE_LANDMARK_DISTANCE_TR(rcvd, landmark_distance);
		}


		if (TOS_NODE_ID == BOTTOM_LEFT_NODE_ID && rcvd->landmark_location == SINK)
		{
			sink_bl_dist = rcvd->landmark_distance;
			call DelayBLSenderTimer.startOneShot(0.5 * 1000);
			//call DelayBLSenderTimer.startOneShot(1 * 1000);	
		}

		if (BOTTOM_RIGHT_NODE_ID == SINK_NODE_ID)
		{
			if (TOS_NODE_ID == TOP_LEFT_NODE_ID && rcvd->landmark_location == SINK)
			{
				sink_br_dist = rcvd->landmark_distance;
				call DelayBRSenderTimer.startOneShot(1.5 * 1000);
				//call DelayBRSenderTimer.startOneShot(2 * 1000);
			}
		}
		else
		{
			if (TOS_NODE_ID == BOTTOM_RIGHT_NODE_ID && rcvd->landmark_location == SINK)
			{
				sink_br_dist = rcvd->landmark_distance;
				call DelayBRSenderTimer.startOneShot(2.5 * 1000);
				//call DelayBRSenderTimer.startOneShot(3 * 1000);
			}
		}

		if (TOS_NODE_ID == TOP_RIGHT_NODE_ID && rcvd->landmark_location == SINK)
		{
			sink_tr_dist = rcvd->landmark_distance;
			call DelayTRSenderTimer.startOneShot(3.5 * 1000);
			//call DelayTRSenderTimer.startOneShot(4 * 1000);
		}


		if (call AwaySeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			call AwaySeqNos.update(rcvd->source_id, rcvd->sequence_number);
			
			METRIC_RCV_AWAY(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.landmark_distance += 1;

			forwarding_message.sink_bl_dist = sink_bl_dist;
			forwarding_message.sink_br_dist = sink_br_dist;
			forwarding_message.sink_tr_dist = sink_tr_dist;

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
		UPDATE_NEIGHBOURS_BL(rcvd, source_addr, landmark_distance_of_bottom_left_sender);
		UPDATE_LANDMARK_DISTANCE_BL(rcvd, landmark_distance_of_bottom_left_sender);
		
		UPDATE_NEIGHBOURS_BR(rcvd, source_addr, landmark_distance_of_bottom_right_sender);
		UPDATE_LANDMARK_DISTANCE_BR(rcvd, landmark_distance_of_bottom_right_sender);

		UPDATE_NEIGHBOURS_TR(rcvd, source_addr, landmark_distance_of_top_right_sender);
		UPDATE_LANDMARK_DISTANCE_TR(rcvd, landmark_distance_of_top_right_sender);

		UPDATE_NEIGHBOURS_SINK(rcvd, source_addr, landmark_distance_of_sink_sender);
		UPDATE_LANDMARK_DISTANCE_SINK(rcvd, landmark_distance_of_sink_sender);
		METRIC_RCV_BEACON(rcvd);
	}

	RECEIVE_MESSAGE_BEGIN(Beacon, Receive)
		case NormalNode:
		case SourceNode:
		case SinkNode: x_receieve_Beacon(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Beacon)
}
