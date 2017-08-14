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

#include <stdlib.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, msg->landmark_distance + 1)
#define METRIC_RCV_BEACON(msg) METRIC_RCV(Beacon, source_addr, BOTTOM, BOTTOM, BOTTOM)

typedef struct
{
	int16_t bottom_left_distance;
	int16_t bottom_right_distance;
	int16_t top_right_distance;
	int16_t sink_distance;
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
	simdbg_clear(name, "[%lu] => addr=%u / bl=%d, br=%d, tr=%d, sink_dist=%d",
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
	dist.bottom_right_distance = BOTTOM; \
	dist.top_right_distance = rcvd->name; \
	dist.sink_distance = BOTTOM; \
	insert_distance_neighbour(&neighbours, source_addr, &dist); \
}

#define UPDATE_NEIGHBOURS_SINK(rcvd, source_addr, name) \
{ \
	distance_container_t dist; \
	dist.bottom_left_distance = BOTTOM; \
	dist.bottom_right_distance = BOTTOM; \
	dist.top_right_distance = BOTTOM; \
	dist.sink_distance = rcvd->name; \
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
	uses interface Random;

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

	uses interface MetricLogging;

	uses interface NodeType;
	uses interface MessageType;

	uses interface AMSend as AwaySend;
	uses interface Receive as AwayReceive;

	uses interface AMSend as BeaconSend;
	uses interface Receive as BeaconReceive;

	uses interface SourcePeriodModel;
	uses interface ObjectDetector;

	uses interface SequenceNumbers as NormalSeqNos;
	uses interface SequenceNumbers as AwaySeqNos;
}

implementation 
{
	enum
	{
		SourceNode, SinkNode, NormalNode
	};

	typedef enum
	{
		UnknownSet = 0, CloserSet = (1 << 0), FurtherSet = (1 << 1), CloserSideSet = (1 << 2), FurtherSideSet = (1 << 3)
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
	}chosen_set_neighbour;

	chosen_set_neighbour chosen_set_neighbours[SLP_MAX_SET_NEIGHBOURS]={{BOTTOM,BOTTOM},{BOTTOM,BOTTOM}};

	typedef struct
	{
		int16_t message_sent;
		int16_t sequence_message_sent;
		int16_t probability;
	}RandomWalk;
	RandomWalk short_random_walk_info = {0, 0, 50};
	RandomWalk long_random_walk_info = {0, 0, 50};

	int16_t landmark_bottom_left_distance = BOTTOM;
	int16_t landmark_bottom_right_distance = BOTTOM;
	int16_t landmark_top_right_distance = BOTTOM;
	int16_t landmark_sink_distance = BOTTOM;

	int16_t sink_bl_dist = BOTTOM;		//sink-bottom_left distance.
	int16_t sink_br_dist = BOTTOM;		//sink-bottom_right distance.
	int16_t sink_tr_dist = BOTTOM;		//sink-top_right distance.

	int16_t dynamic_period_last = 0; //number of messages that node send during dynamic period

	int16_t short_random_walk_hops = BOTTOM;
	int16_t long_random_walk_hops = BOTTOM;

	distance_neighbours_t neighbours;

	bool busy = FALSE;
	message_t packet;

	uint32_t get_source_period()
	{
		assert(call NodeType.get() == SourceNode);
		//simdbgverbose("stdout", "here\n");
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

	int16_t random_number(int16_t num)
	{
		uint16_t rnd = call Random.rand16();
		return rnd % num;
	}

	int16_t get_probability(int16_t t)
	{
		return 100 * pow(0.5,t);
	}


	SetType random_walk_direction()
	{
		uint32_t possible_sets = UnknownSet;

		if (landmark_bottom_left_distance != BOTTOM && landmark_bottom_right_distance != BOTTOM)
		{
			uint32_t i;

			uint32_t FurtherSet_neighbours = 0;
			uint32_t CloserSideSet_neighbours = 0;
			uint32_t CloserSet_neighbours = 0;
			uint32_t FurtherSideSet_neighbours = 0;

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
				else //if (landmark_bottom_left_distance < neighbour->bottom_left_distance && landmark_bottom_right_distance > neighbour->bottom_right_distance)
				{
					CloserSet_neighbours ++;
					FurtherSideSet_neighbours ++;
				}

				if (FurtherSideSet_neighbours >= 1)
				{
					possible_sets |= FurtherSideSet;
				}

				if (CloserSideSet_neighbours >= 1)
				{
					possible_sets |= CloserSideSet;
				}

				if (FurtherSet_neighbours >= 1)
				{
					possible_sets |= FurtherSet; 
				}

				if (CloserSet_neighbours >= 1)
				{
					possible_sets |= CloserSet;
				}
			}
			simdbgverbose("stdout", "CloserSet_neighbours=%d, FurtherSet_neighbours=%d, CloserSideSet_neighbours=%d, FurtherSideSet_neighbours=%d\n",
			CloserSet_neighbours, FurtherSet_neighbours, CloserSideSet_neighbours, FurtherSideSet_neighbours);
		}

		simdbgverbose("stdout", "possible_sets=%d, landmark_bottom_left_distance=%d, landmark_bottom_right_distance=%d, landmark_sink_distance=%d\n", 
				possible_sets, landmark_bottom_left_distance, landmark_bottom_right_distance, landmark_sink_distance);

		if (possible_sets == (CloserSet | FurtherSet | CloserSideSet | FurtherSideSet))
		{	
			uint16_t rnd = call Random.rand16() % 4;
			if(rnd == 0)			return CloserSet;
			else if (rnd == 1)		return FurtherSet;
			else if (rnd == 2)		return CloserSideSet;
			else					return FurtherSideSet;
		}		
		else if (possible_sets == ( FurtherSet | CloserSideSet | FurtherSideSet))
		{
			uint16_t rnd = call Random.rand16() % 3;
			if(rnd == 0)			return FurtherSet;
			else if (rnd == 1)		return CloserSideSet;
			else					return FurtherSideSet;
		}

		else if (possible_sets == (CloserSet  | CloserSideSet | FurtherSideSet))
		{
			uint16_t rnd = call Random.rand16() % 3;
			if(rnd == 0)			return CloserSet;
			else if (rnd == 1)		return CloserSideSet;
			else					return FurtherSideSet;
		}

		else if (possible_sets == (CloserSet | FurtherSet  | FurtherSideSet))
		{
			uint16_t rnd = call Random.rand16() % 3;
			if(rnd == 0)			return CloserSet;
			else if (rnd == 1)		return FurtherSet;
			else					return FurtherSideSet;
		}

		else if (possible_sets == (CloserSet | FurtherSet | CloserSideSet))
		{
			uint16_t rnd = call Random.rand16() % 3;
			if(rnd == 0)			return CloserSet;
			else if (rnd == 1)		return FurtherSet;
			else					return CloserSideSet;			
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

		else if (possible_sets == CloserSet)
		{
			return CloserSet;
		}
		else if (possible_sets == FurtherSet)
		{
			return FurtherSet;
		}

		else if (possible_sets == CloserSideSet)
		{
			return CloserSideSet;
		}
		else if (possible_sets == FurtherSideSet)
		{
			return FurtherSideSet;
		}
		else
		{
			simdbgverbose("stdout","possible set = 0, return UnknownSet.\n");
			return UnknownSet;		
		}
	}

	SetType neighbour_check(SetType further_or_closer_set, const am_addr_t* to_ignore, size_t to_ignore_length)
	{
		uint32_t k;

		distance_neighbours_t local_neighbours;
		init_distance_neighbours(&local_neighbours);

		// If we don't know our sink distance then we cannot work
		// out which neighbour is in closer or further.
		if (landmark_bottom_left_distance != BOTTOM && landmark_bottom_right_distance != BOTTOM && further_or_closer_set != UnknownSet)
		{
			for (k = 0; k != neighbours.size; ++k)
			{
				distance_neighbour_detail_t const* const neighbour = &neighbours.data[k];

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

				if ((further_or_closer_set == FurtherSet && landmark_bottom_right_distance < neighbour->contents.bottom_right_distance) ||
					(further_or_closer_set == CloserSet && landmark_bottom_right_distance >= neighbour->contents.bottom_right_distance) ||
					(further_or_closer_set == FurtherSideSet && landmark_bottom_left_distance < neighbour->contents.bottom_left_distance) ||
					(further_or_closer_set == CloserSideSet && landmark_bottom_left_distance >= neighbour->contents.bottom_left_distance))
				{
					insert_distance_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
				}
			}
		}
		if (local_neighbours.size == 0)
		{
			simdbgverbose("stdout","Need change Set.\n");
			return CloserSet;
		}
		else
		{
			simdbgverbose("stdout", "<neighbour check>set type:%d, local neighbour size: %u\n",further_or_closer_set, local_neighbours.size);
			return further_or_closer_set;
		}
	}

	// node forward message choosing from one neighour address from  the chosen set.
	am_addr_t random_walk_target(SetType further_or_closer_set, const am_addr_t* to_ignore, size_t to_ignore_length)
	{
		am_addr_t chosen_address;
		uint32_t k;

		distance_neighbours_t local_neighbours;
		distance_neighbour_detail_t* neighbour_target;
		init_distance_neighbours(&local_neighbours);

		// If we don't know our sink distance then we cannot work
		// out which neighbour is in closer or further.
		if (landmark_bottom_left_distance != BOTTOM && landmark_bottom_right_distance != BOTTOM && further_or_closer_set != UnknownSet)
		{
			for (k = 0; k != neighbours.size; ++k)
			{
				distance_neighbour_detail_t const* const neighbour = &neighbours.data[k];

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

				if ((further_or_closer_set == FurtherSet && landmark_bottom_right_distance < neighbour->contents.bottom_right_distance) ||
					(further_or_closer_set == CloserSet && landmark_bottom_right_distance >= neighbour->contents.bottom_right_distance) ||
					(further_or_closer_set == FurtherSideSet && landmark_bottom_left_distance < neighbour->contents.bottom_left_distance) ||
					(further_or_closer_set == CloserSideSet && landmark_bottom_left_distance >= neighbour->contents.bottom_left_distance))
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

			// initialise chosen_set_neighbours from node_neighbours.
			for (m=0; m != SLP_MAX_1_HOP_NEIGHBOURHOOD; ++m)
			{
				for(j=0; j!= SLP_MAX_SET_NEIGHBOURS; ++j)
				{
					if (node_neighbours[m].address == local_neighbours.data[j].address)
					{
						chosen_set_neighbours[j].address = local_neighbours.data[j].address;
						chosen_set_neighbours[j].neighbour_size = node_neighbours[m].neighbour_size;
						simdbgverbose("stdout", "chosen_set_neighbours: neighbour[%d], address is %d, neighbour_size is %d\n",
							j, chosen_set_neighbours[j].address, chosen_set_neighbours[j].neighbour_size);
					}
				}
			}

			if (chosen_set_neighbours[0].neighbour_size == chosen_set_neighbours[1].neighbour_size)
			{
				// Choose a neighbour with equal probabilities.
				const uint16_t rnd = call Random.rand16();
				const uint16_t neighbour_index = rnd % local_neighbours.size;
				neighbour_target = &local_neighbours.data[neighbour_index];
				simdbgverbose("stdout","randomly pick one. Chosen:%d\n", neighbour_target->address);
			}
			else
			{
				neighbour_target = (chosen_set_neighbours[0].neighbour_size < chosen_set_neighbours[1].neighbour_size)? &local_neighbours.data[0]: &local_neighbours.data[1];
				simdbgverbose("stdout", "pick smaller one: %d\n", neighbour_target->address);
			} 

			chosen_address = neighbour_target->address;
		}

		return chosen_address;
	}

	uint32_t beacon_send_wait()
	{
		return 75U + (uint32_t)(50U * random_float());
	}

	USE_MESSAGE_NO_EXTRA_TO_SEND(Normal);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Away);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Beacon);

	event void Boot.booted()
	{
		LOG_STDOUT_VERBOSE(EVENT_BOOTED, "booted\n");

		init_distance_neighbours(&neighbours);

		call MessageType.register_pair(NORMAL_CHANNEL, "Normal");
		call MessageType.register_pair(AWAY_CHANNEL, "Away");
		call MessageType.register_pair(BEACON_CHANNEL, "Beacon");

		call NodeType.register_pair(SourceNode, "SourceNode");
		call NodeType.register_pair(SinkNode, "SinkNode");
		call NodeType.register_pair(NormalNode, "NormalNode");

		if (call NodeType.is_node_sink())
		{
			call NodeType.init(SinkNode);
		}
		else
		{
			call NodeType.init(NormalNode);
		}

		call RadioControl.start();
	}

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			LOG_STDOUT_VERBOSE(EVENT_RADIO_ON, "radio on\n");

			call ObjectDetector.start();

			if (call NodeType.get() == SinkNode)
			{
				call AwaySenderTimer.startOneShot(1 * 1000); // One second
			}

			if (call NodeType.is_topology_node_id(BOTTOM_LEFT_NODE_ID))
			{
				call DelayBLSenderTimer.startOneShot(3 * 1000);	
			}

			if (call NodeType.is_topology_node_id(BOTTOM_RIGHT_NODE_ID))
			{
				call DelayBRSenderTimer.startOneShot(5 * 1000);	
			}
		
			if (call NodeType.is_topology_node_id(TOP_RIGHT_NODE_ID))
			{
				call DelayTRSenderTimer.startOneShot(7 * 1000);
			}
		}
		else
		{
			ERROR_OCCURRED(ERROR_RADIO_CONTROL_START_FAIL, "RadioControl failed to start, retrying.\n");

			call RadioControl.start();
		}
	}

	event void RadioControl.stopDone(error_t err)
	{
		LOG_STDOUT_VERBOSE(EVENT_RADIO_OFF, "radio off\n");
	}

	event void ObjectDetector.detect()
	{
		// A sink node cannot become a source node
		if (call NodeType.get() != SinkNode)
		{
			call NodeType.set(SourceNode);

			call BroadcastNormalTimer.startOneShot(10 * 1000);	//wait till beacon messages send finished.
		}
	}

	event void ObjectDetector.stoppedDetecting()
	{
		if (call NodeType.get() == SourceNode)
		{
			call BroadcastNormalTimer.stop();

			call NodeType.set(NormalNode);
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

		if (send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			call AwaySeqNos.increment(TOS_NODE_ID);
		}
	}

	event void SourcePeriodModel.fired()
	{
	}

	event void BroadcastNormalTimer.fired()
	{
		NormalMessage message;
		am_addr_t target;
		int16_t half_sink_source_dist = landmark_sink_distance/2 -1;
		int16_t wait_before_short_delay_ms = 3 * half_sink_source_dist * NODE_TRANSMIT_TIME;

		const uint32_t source_period = get_source_period();

		simdbgverbose("stdout", "call BroadcastNormalTimer.fired, source_period: %u\n", source_period);

		simdbgverbose("SourceBroadcasterC", "%s: BroadcastNormalTimer fired.\n", sim_time_string());

		short_random_walk_hops = call Random.rand16() % half_sink_source_dist + 2;
		long_random_walk_hops = call Random.rand16() % half_sink_source_dist + landmark_sink_distance + 2;		

		if (short_random_walk_info.message_sent - LONG_RANDOM_WALK_RECEIVE_RATIO * long_random_walk_info.message_sent >= half_sink_source_dist)
		{
			//dymaic period here.
			if (dynamic_period_last <= landmark_sink_distance)
			{
				//printf("dynamic_period\n");
				message.random_walk_hops = long_random_walk_hops;
				dynamic_period_last += 1;
			}
			//reset the count.
			else
			{
				int16_t ran = random_number(100);
				short_random_walk_info.message_sent = 0;
				long_random_walk_info.message_sent = 0;
				long_random_walk_info.sequence_message_sent = 0;
				short_random_walk_info.sequence_message_sent = 0;
				dynamic_period_last = 0;

				//printf("reset\n");

				if ( ran< get_probability(short_random_walk_info.sequence_message_sent+1))
				{
					//printf("%s: short random walk, probability: %d, short max probability: %d\n", sim_time_string(), ran, short_random_walk_info.probability);
					message.random_walk_hops = short_random_walk_hops;
					short_random_walk_info.message_sent += 1;
					short_random_walk_info.sequence_message_sent += 1;
					long_random_walk_info.sequence_message_sent = 0;
				}
				else
				{
					//printf("%s: long random walk, probability: %d, short max probability: %d\n", sim_time_string(), ran, short_random_walk_info.probability);
					message.random_walk_hops = long_random_walk_hops;
					long_random_walk_info.message_sent += 1;
					long_random_walk_info.sequence_message_sent += 1;
					short_random_walk_info.sequence_message_sent = 0;
				}
			}
		}
		//normal period
		else
		{
			int16_t ran = random_number(100);
			if (ran < short_random_walk_info.probability)
			{
				message.random_walk_hops = short_random_walk_hops;
				short_random_walk_info.message_sent += 1;
				short_random_walk_info.sequence_message_sent += 1;
				long_random_walk_info.sequence_message_sent = 0;
				short_random_walk_info.probability = get_probability(short_random_walk_info.sequence_message_sent+1);
				long_random_walk_info.probability = 100 - short_random_walk_info.probability;
				//printf("%s: short random walk, probability: %d, short max probability: %d\n", sim_time_string(), ran, short_random_walk_info.probability);
			}
			else
			{
				message.random_walk_hops = long_random_walk_hops;
				long_random_walk_info.message_sent += 1;
				long_random_walk_info.sequence_message_sent += 1;
				short_random_walk_info.sequence_message_sent = 0;
				long_random_walk_info.probability = get_probability(long_random_walk_info.sequence_message_sent+1);
				short_random_walk_info.probability = 100 - long_random_walk_info.probability;
				//printf("%s: long random walk, probability: %d, short max probability: %d\n", sim_time_string(), ran, short_random_walk_info.probability);
			}
		}

		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;

		message.landmark_distance_of_bottom_left_sender = landmark_bottom_left_distance;
		message.landmark_distance_of_bottom_right_sender = landmark_bottom_right_distance;
		message.landmark_distance_of_top_right_sender = landmark_top_right_distance;
		message.landmark_distance_of_sink_sender = landmark_sink_distance;

		message.neighbour_size = neighbours.size;

		message.further_or_closer_set = random_walk_direction();

		target = random_walk_target(message.further_or_closer_set, NULL, 0);
			
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
			simdbgverbose("stdout", "target is AM_BROADCAST_ADDR\n");
			simdbg("M-SD", NXSEQUENCE_NUMBER_SPEC "\n", message.sequence_number);
		}

		//if last message is long random walk message, delay to send.
		if (long_random_walk_info.sequence_message_sent == 1 && short_random_walk_info.sequence_message_sent == 0)
		{
			//printf("call startOneShot(WAIT_BEFORE_SHORT_MS + source_period)\n");
			call BroadcastNormalTimer.startOneShot(wait_before_short_delay_ms + source_period);
		}
		else
		{
			//printf("call startOneShot(source_period)\n");
			call BroadcastNormalTimer.startOneShot(source_period);
		}
	}

	event void AwaySenderTimer.fired()
	{
		AwayMessage message;

		if (call NodeType.get() == SinkNode)
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

		message.neighbour_size = neighbours.size;
		message.node_id = TOS_NODE_ID;

		call Packet.clear(&packet);

		if (send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			call AwaySeqNos.increment(TOS_NODE_ID);
		}
	}

	event void BeaconSenderTimer.fired()
	{
		BeaconMessage message;

		simdbgverbose("SourceBroadcasterC", "BeaconSenderTimer fired.\n");

		message.landmark_distance_of_bottom_left_sender = landmark_bottom_left_distance;
		message.landmark_distance_of_bottom_right_sender = landmark_bottom_right_distance;
		message.landmark_distance_of_top_right_sender = landmark_top_right_distance;
		message.landmark_distance_of_sink_sender = landmark_sink_distance;

		message.neighbour_size = neighbours.size;
		message.node_id = TOS_NODE_ID;

		call Packet.clear(&packet);

		send_Beacon_message(&message, AM_BROADCAST_ADDR);
	}

	void process_normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		int16_t i;

		UPDATE_LANDMARK_DISTANCE_BL(rcvd, landmark_distance_of_bottom_left_sender);
		UPDATE_LANDMARK_DISTANCE_BR(rcvd, landmark_distance_of_bottom_right_sender);
		UPDATE_LANDMARK_DISTANCE_TR(rcvd, landmark_distance_of_top_right_sender);
		UPDATE_LANDMARK_DISTANCE_SINK(rcvd, landmark_distance_of_sink_sender);
		
		UPDATE_NEIGHBOURS_BL(rcvd, source_addr, landmark_distance_of_bottom_left_sender);
		UPDATE_NEIGHBOURS_BR(rcvd, source_addr, landmark_distance_of_bottom_right_sender);
		UPDATE_NEIGHBOURS_TR(rcvd, source_addr, landmark_distance_of_top_right_sender);		
		UPDATE_NEIGHBOURS_SINK(rcvd, source_addr, landmark_distance_of_sink_sender);

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

			if (rcvd->source_distance + 1 < rcvd->random_walk_hops && !rcvd->broadcast)
			{
				am_addr_t target;

				// The previous node(s) were unable to choose a direction,
				// so lets try to work out the direction the message should go in.
				if (forwarding_message.further_or_closer_set == UnknownSet)
				{
					forwarding_message.further_or_closer_set = random_walk_direction();
				}


				//if chosen size is 0, choose the other set.
				forwarding_message.further_or_closer_set = neighbour_check(rcvd->further_or_closer_set, &source_addr, 1);

				// Get a target, ignoring the node that sent us this message
				target = random_walk_target(forwarding_message.further_or_closer_set, &source_addr, 1);

				//if (reach_borderline == TRUE && forwarding_message.further_or_closer_set != CloserSet)
				//{
					//forwarding_message.further_or_closer_set = CloserSet;
				//	target = random_walk_target(forwarding_message.further_or_closer_set, &source_addr, 1);
				//}
				
				forwarding_message.broadcast = (target == AM_BROADCAST_ADDR);

				// A node on the path away from, or towards the landmark node
				// doesn't have anyone to send to.
				// We do not want to broadcast here as it may lead the attacker towards the source.
				if (target == AM_BROADCAST_ADDR)
				{
					//TODO: decide whether message choose new direction or broadcast.
					//return;
				}
				// if the message reach the sink, do not need flood.
				if (call NodeType.get() == SinkNode)
				{
					return;
				}

				simdbgverbose("stdout", "Forwarding normal from %u to target = %u\n",
					TOS_NODE_ID, target);

				call Packet.clear(&packet);

				send_Normal_message(&forwarding_message, target);
			}
			else
			{
				if (!rcvd->broadcast && rcvd->source_distance + 1 == rcvd->random_walk_hops)
				{
					simdbg("Metric-PATH-END", TOS_NODE_ID_SPEC "," TOS_NODE_ID_SPEC "," NXSEQUENCE_NUMBER_SPEC ",%u\n",
						source_addr, rcvd->source_id, rcvd->sequence_number, rcvd->source_distance + 1);
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

		if (call NodeType.is_topology_node_id(BOTTOM_LEFT_NODE_ID) && rcvd->landmark_location == SINK)
		{
			sink_bl_dist = rcvd->landmark_distance;	
		}

		if (call NodeType.is_topology_node_id(BOTTOM_RIGHT_NODE_ID) && rcvd->landmark_location == SINK)
		{
			sink_br_dist = rcvd->landmark_distance;	
		}
		
		if (call NodeType.is_topology_node_id(TOP_RIGHT_NODE_ID) && rcvd->landmark_location == SINK)
		{
			sink_tr_dist = rcvd->landmark_distance;
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
			
			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);

			call BeaconSenderTimer.startOneShot(beacon_send_wait());
		}
	}

	RECEIVE_MESSAGE_BEGIN(Away, Receive)
		case NormalNode:
		case SourceNode:
		case SinkNode: x_receive_Away(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Away)

	void x_receieve_Beacon(message_t* msg, const BeaconMessage* const rcvd, am_addr_t source_addr)
	{
		int16_t i;

		UPDATE_NEIGHBOURS_BL(rcvd, source_addr, landmark_distance_of_bottom_left_sender);
		UPDATE_LANDMARK_DISTANCE_BL(rcvd, landmark_distance_of_bottom_left_sender);
		
		UPDATE_NEIGHBOURS_BR(rcvd, source_addr, landmark_distance_of_bottom_right_sender);
		UPDATE_LANDMARK_DISTANCE_BR(rcvd, landmark_distance_of_bottom_right_sender);

		UPDATE_NEIGHBOURS_TR(rcvd, source_addr, landmark_distance_of_top_right_sender);
		UPDATE_LANDMARK_DISTANCE_TR(rcvd, landmark_distance_of_top_right_sender);

		UPDATE_NEIGHBOURS_SINK(rcvd, source_addr, landmark_distance_of_sink_sender);
		UPDATE_LANDMARK_DISTANCE_SINK(rcvd, landmark_distance_of_sink_sender);

		METRIC_RCV_BEACON(rcvd);

		for (i=0; i!=SLP_MAX_1_HOP_NEIGHBOURHOOD; i++)
		{
			// if node neighbour size is larger than previous one, update it to the new one.
			if(node_neighbours[i].address == rcvd->node_id)
			{
				node_neighbours[i].neighbour_size = (node_neighbours[i].neighbour_size <= rcvd->neighbour_size)? 
				rcvd->neighbour_size: node_neighbours[i].neighbour_size;
				//have updated the neighbour size, so no need to continue the loop, so break.
				break;
			}
			// if neighbour size info is not recorded, add it.
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