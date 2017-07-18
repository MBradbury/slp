/*
The codes are used for SAC17 paper.
Key features include:
- divide neighbours into 4 sets.
- use three landmark nodes to decide network topology (SinkCorner or SourceCorner).
- specify the short and long random walk counts.
- specify the order of ShortLong or LongShort.
- short random walk message delay after a long random walk message.
- use a direction bias factor for bias random walk.
- bias random walk could choose H or V direction.
- the length of short and long random walks are fixed.
*/

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
		bottom_left_distance = minbot(bottom_left_distance, botinc(rcvd->name)); \
	} \
}

#define UPDATE_LANDMARK_DISTANCE_BR(rcvd, name) \
{ \
	if (rcvd->name != BOTTOM) \
	{ \
		bottom_right_distance = minbot(bottom_right_distance, botinc(rcvd->name)); \
	} \
}

#define UPDATE_LANDMARK_DISTANCE_TR(rcvd, name) \
{ \
	if (rcvd->name != BOTTOM) \
	{ \
		top_right_distance = minbot(top_right_distance, botinc(rcvd->name)); \
	} \
}

#define UPDATE_LANDMARK_DISTANCE_SINK(rcvd, name) \
{ \
	if (rcvd->name != BOTTOM) \
	{ \
		sink_distance = minbot(sink_distance, botinc(rcvd->name)); \
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

	uses interface MetricLogging;

	uses interface NodeType;
	uses interface MessageType;
	uses interface SourcePeriodModel;
	uses interface ObjectDetector;

	uses interface SequenceNumbers as NormalSeqNos;
	uses interface SequenceNumbers as AwaySeqNos;
	 
	uses interface Random;
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

	typedef enum
	{
		UnknownSinkLocation, Centre, Others 
	}SinkLocation;
	SinkLocation sink_location = UnknownSinkLocation;

	typedef enum
	{
		UnknownBiasDirection, H, V 
	}BiasedType;
	BiasedType bias_direction = UnknownBiasDirection;

	typedef enum
	{
		UnknownMessageType, ShortRandomWalk, LongRandomWalk
	}WalkType;
	WalkType messagetype = UnknownMessageType;
	WalkType nextmessagetype = UnknownMessageType;

	bool reach_borderline = FALSE;

	int16_t bottom_left_distance = BOTTOM;
	int16_t bottom_right_distance = BOTTOM;
	int16_t top_right_distance = BOTTOM;
	int16_t sink_distance = BOTTOM;

	int16_t sink_bl_dist = BOTTOM;		//sink-bottom_left distance.
	int16_t sink_br_dist = BOTTOM;		//sink-bottom_right distance.
	int16_t sink_tr_dist = BOTTOM;		//sink-top_right distance.

	int16_t srw_count = 0;	//short random walk count.
	int16_t lrw_count = 0;	//long random walk count.

	distance_neighbours_t neighbours;

	unsigned int extra_to_send = 0;

	bool busy = FALSE;
	message_t packet;

	uint32_t get_source_period()
	{
		assert(call NodeType.get() == SourceNode);
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

	void sink_location_check()
	{
		int16_t bl_br_dist;
		int16_t bl_tr_dist;
		int16_t br_tr_dist;

		if (sink_bl_dist != BOTTOM && sink_br_dist != BOTTOM && sink_tr_dist != BOTTOM)
		{
			bl_br_dist = abs_generic(sink_bl_dist - sink_br_dist);
			bl_tr_dist = abs_generic(sink_bl_dist - sink_tr_dist);
			br_tr_dist = abs_generic(sink_br_dist - sink_tr_dist);
	
			if ( bl_br_dist <= CENTRE_AREA && bl_tr_dist <= CENTRE_AREA && br_tr_dist <= CENTRE_AREA )
				sink_location = Centre;
			else
				sink_location = Others;
		}
		else
			sink_location = Others;
	}

	// return how many 1 in a number
	int16_t bitcount(int16_t n)
	{
		int16_t count = 0;
		while(n)
		{
			count++;
			n &= (n-1);
		}
		return count;
	}

	SetType random_walk_direction()
	{
		uint32_t possible_sets = UnknownSet;
		uint16_t rnd;

		if (bottom_left_distance != BOTTOM && bottom_right_distance != BOTTOM)
		{
			uint32_t i;

			uint32_t FurtherSet_neighbours = 0;
			uint32_t CloserSideSet_neighbours = 0;
			uint32_t CloserSet_neighbours = 0;
			uint32_t FurtherSideSet_neighbours = 0;

			for (i = 0; i != neighbours.size; ++i)
			{
				distance_container_t const* const neighbour = &neighbours.data[i].contents;

				if (bottom_left_distance < neighbour->bottom_left_distance && bottom_right_distance <  neighbour->bottom_right_distance)
				{
					FurtherSet_neighbours ++;
					FurtherSideSet_neighbours ++;					
				}
				else if (bottom_left_distance > neighbour->bottom_left_distance && bottom_right_distance < neighbour->bottom_right_distance)
				{
					CloserSideSet_neighbours ++;
					FurtherSet_neighbours ++;
				}
				else if (bottom_left_distance > neighbour->bottom_left_distance && bottom_right_distance >  neighbour->bottom_right_distance)
				{
					CloserSet_neighbours ++;
					CloserSideSet_neighbours ++;				
				}
				else //if (bottom_left_distance < neighbour->bottom_left_distance && bottom_right_distance > neighbour->bottom_right_distance)
				{
					CloserSet_neighbours ++;
					FurtherSideSet_neighbours ++;
				}

				possible_sets = CloserSet|FurtherSet|CloserSideSet|FurtherSideSet;
			}
		}
		
		rnd = call Random.rand16() % bitcount(possible_sets) + 1;
		return (possible_sets >> rnd) + 1;
	}

	am_addr_t random_walk_target(SetType further_or_closer_set, BiasedType biased_direction, const am_addr_t* to_ignore, size_t to_ignore_length)
	{
		am_addr_t chosen_address;
		uint32_t k;

		distance_neighbours_t local_neighbours;
		init_distance_neighbours(&local_neighbours);

		if (further_or_closer_set == UnknownSet)
			return AM_BROADCAST_ADDR;

		// If we don't know our sink distance then we cannot work
		// out which neighbour is in closer or further.
		if (bottom_left_distance != BOTTOM && bottom_right_distance != BOTTOM && further_or_closer_set != UnknownSet)
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

				if ((further_or_closer_set == FurtherSet && bottom_right_distance < neighbour->contents.bottom_right_distance) ||
					(further_or_closer_set == CloserSet && bottom_right_distance >= neighbour->contents.bottom_right_distance) ||
					(further_or_closer_set == FurtherSideSet && bottom_left_distance < neighbour->contents.bottom_left_distance) ||
					(further_or_closer_set == CloserSideSet && bottom_left_distance >= neighbour->contents.bottom_left_distance))
				{
					insert_distance_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
				}
			}
		}

		if (local_neighbours.size == 0)
		{
			//simdbgverbose("stdout", "No local neighbours to choose so broadcasting. (my-dist=%d, my-neighbours-size=%u)\n",
			//	bottom_left_distance, neighbours.size);
			chosen_address = AM_BROADCAST_ADDR;
		}
		else
		{
			distance_neighbour_detail_t*  neighbour;

			uint16_t rnd = call Random.rand16();
			uint16_t neighbour_index = rnd % local_neighbours.size; ////randomly choose neighbour index
			uint16_t brn = rnd % 100; 	//bias random number;

			if (sink_location == UnknownSinkLocation)
			{
				sink_location_check();
			}

			if (sink_location == Centre && further_or_closer_set == CloserSet)	//deal with biased random walk here.
			{
				if (biased_direction == UnknownBiasDirection)
				{
					neighbour = &local_neighbours.data[neighbour_index];  //randomly choose one neighbour

					//determine the neighbour is V or H.
					if (bottom_left_distance > neighbour->contents.bottom_left_distance)
						bias_direction = V;
					else if (bottom_left_distance < neighbour->contents.bottom_left_distance)
						bias_direction = H;
					else
						simdbgerror("stdout","biased direction error!\n");

					chosen_address = neighbour->address;
				}
				else	//bias_direction is H or bias_direction is V.
				{
					for (k = 0; k != local_neighbours.size; ++k)
					{
						neighbour = &local_neighbours.data[k];
						if(biased_direction == H)
						{
							if (bottom_left_distance < neighbour->contents.bottom_left_distance && brn < BIASED_NO)
							{
								chosen_address = neighbour->address;
								break;
							}
							else	;
						}
						else		//biased_direction is V
						{
							if (bottom_left_distance > neighbour->contents.bottom_left_distance && brn < BIASED_NO)
							{
								chosen_address = neighbour->address;
								break;
							}
							else	;
						}

						chosen_address = neighbour->address;
					}
				}
			}
			else	//normal case.
			{
				if(local_neighbours.size == 1 && further_or_closer_set != CloserSet)
				{
					reach_borderline = TRUE;
				}
				else
				{
					neighbour = &local_neighbours.data[neighbour_index];
					chosen_address = neighbour->address;
				}
			}
			//simdbgverbose("stdout","sink_bl_dist=%d, sink_br_dist=%d, sink_tr_dist=%d\n", sink_bl_dist, sink_br_dist, sink_tr_dist);
		}

		//simdbgverbose("stdout", "Location:%u, biased_direction:%u, Chosen %u at index %u (rnd=%u) out of %u neighbours\n",
		//		sink_location, biased_direction, chosen_address, neighbour_index, rnd, local_neighbours.size);

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

	WalkType sl_next_message_type(int16_t srw, int16_t lrw)
	{
		WalkType sl_type;

		if (srw == 0 && lrw != 0)
			sl_type = LongRandomWalk;
		else
			sl_type = ShortRandomWalk;

		return sl_type;
	}

	WalkType ls_next_message_type(int16_t srw, int16_t lrw)
	{
		WalkType ls_type;

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

	USE_MESSAGE_NO_EXTRA_TO_SEND(Normal);
	USE_MESSAGE(Away);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Beacon);

	event void Boot.booted()
	{
		simdbgverbose("Boot", "Application booted.\n");

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
			if (TOS_NODE_ID == BOTTOM_LEFT_NODE_ID)
			{
				call DelayBLSenderTimer.startOneShot(3 * 1000);	
			}

			if (TOS_NODE_ID == BOTTOM_RIGHT_NODE_ID )
			{
				call DelayBRSenderTimer.startOneShot(5 * 1000);	
			}
		
			if (TOS_NODE_ID == TOP_RIGHT_NODE_ID )
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

		bottom_left_distance = 0;
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

		bottom_right_distance = 0;
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

		top_right_distance = 0;
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

		const uint32_t source_period = get_source_period();

		simdbgverbose("SourceBroadcasterC", "BroadcastNormalTimer fired.\n");

#ifdef SLP_VERBOSE_DEBUG
		print_distance_neighbours("stdout", &neighbours);
#endif

		if (srw_count == 0 && lrw_count == 0)
		{
			srw_count = SHORT_COUNT;
			lrw_count = LONG_COUNT;
		}

		#ifdef SHORT_LONG_SEQUENCE
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


		if (message.random_walk_hops == RANDOM_WALK_HOPS)
		{
			messagetype = ShortRandomWalk;
		}
		else
		{
			messagetype = LongRandomWalk;
		}

		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;
		message.biased_direction = 0;	//initialise the biased_direction when first generate message.

		message.landmark_distance_of_bottom_left_sender = bottom_left_distance;
		message.landmark_distance_of_bottom_right_sender = bottom_right_distance;
		message.landmark_distance_of_top_right_sender = top_right_distance;
		message.landmark_distance_of_sink_sender = sink_distance;

		message.further_or_closer_set = random_walk_direction();

		target = random_walk_target(message.further_or_closer_set, message.biased_direction, NULL, 0);

		message.biased_direction = bias_direction;		//initialise biased_direction as UnknownBiasDirection. 

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
			simdbg("Metric-SOURCE_DROPPED", NXSEQUENCE_NUMBER_SPEC "\n",
				message.sequence_number);
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

		if (call NodeType.get() == SinkNode)
		{
			sink_distance = 0;
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

		if (send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			call AwaySeqNos.increment(TOS_NODE_ID);
		}

	}

	event void BeaconSenderTimer.fired()
	{
		BeaconMessage message;

		simdbgverbose("SourceBroadcasterC", "BeaconSenderTimer fired.\n");

		message.landmark_distance_of_bottom_left_sender = bottom_left_distance;
		message.landmark_distance_of_bottom_right_sender = bottom_right_distance;
		message.landmark_distance_of_top_right_sender = top_right_distance;
		message.landmark_distance_of_sink_sender = sink_distance;

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

			forwarding_message.landmark_distance_of_bottom_left_sender = bottom_left_distance;
			forwarding_message.landmark_distance_of_bottom_right_sender = bottom_right_distance;
			forwarding_message.landmark_distance_of_top_right_sender = top_right_distance;
			forwarding_message.landmark_distance_of_sink_sender = sink_distance;

			if (rcvd->source_distance + 1 < rcvd->random_walk_hops && !rcvd->broadcast)
			{
				am_addr_t target;

				// The previous node(s) were unable to choose a direction,
				// so lets try to work out the direction the message should go in.
				if (forwarding_message.further_or_closer_set == UnknownSet)
				{
					forwarding_message.further_or_closer_set = random_walk_direction();
				}

				// Get a target, ignoring the node that sent us this message
				target = random_walk_target(forwarding_message.further_or_closer_set,forwarding_message.biased_direction, &source_addr, 1);
				
				if (reach_borderline == TRUE && forwarding_message.further_or_closer_set != CloserSet)
				{
					forwarding_message.further_or_closer_set = CloserSet;
					target = random_walk_target(forwarding_message.further_or_closer_set, forwarding_message.biased_direction, &source_addr, 1);
				}
				//target = random_walk_target(forwarding_message.further_or_closer_set,forwarding_message.biased_direction, &source_addr, 1);
				
				forwarding_message.broadcast = (target == AM_BROADCAST_ADDR);

				// A node on the path away from, or towards the landmark node
				// doesn't have anyone to send to.
				// We do not want to broadcast here as it may lead the attacker towards the source.
				if (target == AM_BROADCAST_ADDR)
				{
					return;
				}
				// if the message reach the sink, do not need flood.
				if (call NodeType.get() == SinkNode)
				{
					return;
				}

				simdbgverbose("stdout", "%s: Forwarding normal from %u to target = %u\n",
					sim_time_string(), TOS_NODE_ID, target);

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