#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"
#include "NeighbourDetail.h"

#include "NormalMessage.h"
#include "AwayMessage.h"
#include "BeaconMessage.h"

#include "MessageQueueInfo.h"
#include "SeqNoWithFlag.h"

#include "HopDistance.h"

#include <Timer.h>
#include <TinyError.h>
#include <math.h>
#include <unistd.h>
#include <string.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, hop_distance_increment(msg->source_distance))
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, hop_distance_increment(msg->landmark_distance))

#define METRIC_RCV_BEACON(msg) METRIC_RCV(Beacon, source_addr, AM_BROADCAST_ADDR, UNKNOWN_SEQNO, UNKNOWN_HOP_DISTANCE)

typedef struct
{
	hop_distance_t bottom_left_distance;
	hop_distance_t bottom_right_distance;
	hop_distance_t sink_distance;
} distance_container_t;

void distance_update(distance_container_t* find, distance_container_t const* given)
{
	find->bottom_left_distance = hop_distance_min(find->bottom_left_distance, given->bottom_left_distance);
	find->bottom_right_distance = hop_distance_min(find->bottom_right_distance, given->bottom_right_distance);
	find->sink_distance = hop_distance_min(find->sink_distance, given->sink_distance);
}

void distance_print(const char* name, size_t i, am_addr_t address, distance_container_t const* contents)
{
	simdbg_clear(name, "[%d] => addr=%u / bl=%d, br=%d, sink_dist=%d",
		TOS_NODE_ID, address, contents->bottom_left_distance, contents->bottom_right_distance, contents->sink_distance);
}

DEFINE_NEIGHBOUR_DETAIL(distance_container_t, distance, distance_update, distance_print, SLP_MAX_1_HOP_NEIGHBOURHOOD);

#define UPDATE_NEIGHBOURS_BL(rcvd, source_addr, name) \
{ \
	distance_container_t dist; \
	dist.bottom_left_distance = rcvd->name; \
	dist.bottom_right_distance = UNKNOWN_HOP_DISTANCE; \
	dist.sink_distance = UNKNOWN_HOP_DISTANCE; \
	insert_distance_neighbour(&neighbours, source_addr, &dist); \
}

#define UPDATE_NEIGHBOURS_BR(rcvd, source_addr, name) \
{ \
	distance_container_t dist; \
	dist.bottom_left_distance = UNKNOWN_HOP_DISTANCE; \
	dist.bottom_right_distance = rcvd->name; \
	dist.sink_distance = UNKNOWN_HOP_DISTANCE; \
	insert_distance_neighbour(&neighbours, source_addr, &dist); \
}

#define UPDATE_NEIGHBOURS_SINK(rcvd, source_addr, name) \
{ \
	distance_container_t dist; \
	dist.bottom_left_distance = UNKNOWN_HOP_DISTANCE; \
	dist.bottom_right_distance = UNKNOWN_HOP_DISTANCE; \
	dist.sink_distance = rcvd->name; \
	insert_distance_neighbour(&neighbours, source_addr, &dist); \
}

#define UPDATE_LANDMARK_DISTANCE_BL(rcvd, name) \
{ \
	if (rcvd->name != UNKNOWN_HOP_DISTANCE) \
	{ \
		landmark_bottom_left_distance = hop_distance_min(landmark_bottom_left_distance, hop_distance_increment(rcvd->name)); \
	} \
}

#define UPDATE_LANDMARK_DISTANCE_BR(rcvd, name) \
{ \
	if (rcvd->name != UNKNOWN_HOP_DISTANCE) \
	{ \
		landmark_bottom_right_distance = hop_distance_min(landmark_bottom_right_distance, hop_distance_increment(rcvd->name)); \
	} \
}

#define UPDATE_LANDMARK_DISTANCE_SINK(rcvd, name) \
{ \
	if (rcvd->name != UNKNOWN_HOP_DISTANCE) \
	{ \
		landmark_sink_distance = hop_distance_min(landmark_sink_distance, hop_distance_increment(rcvd->name)); \
	} \
}

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;

	uses interface Timer<TMilli> as ConsiderTimer;
	uses interface Timer<TMilli> as BroadcastNormalTimer;
	uses interface Timer<TMilli> as AwaySenderTimer;
	uses interface Timer<TMilli> as DelayBLSenderTimer;
	uses interface Timer<TMilli> as DelayBRSenderTimer;
	uses interface Timer<TMilli> as BeaconSenderTimer;

	uses interface Packet;
	uses interface AMPacket;

	uses interface SplitControl as RadioControl;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;
	uses interface Receive as NormalSnoop;
	uses interface PacketAcknowledgements as NormalPacketAcknowledgements;

	uses interface MetricLogging;
	uses interface MetricHelpers;

	uses interface NodeType;
	uses interface MessageType;

	uses interface AMSend as AwaySend;
	uses interface Receive as AwayReceive;

	uses interface AMSend as BeaconSend;
	uses interface Receive as BeaconReceive;

	uses interface ObjectDetector;

	uses interface SequenceNumbers as NormalSeqNos;
	uses interface SequenceNumbers as AwaySeqNos;

	uses interface Cache<SeqNoWithAddr> as LruNormalSeqNos;

	uses interface LocalTime<TMilli>;

	// Messages that are queued to send
	uses interface Dictionary<SeqNoWithAddr, message_queue_info_t*> as MessageQueue;
    uses interface Pool<message_queue_info_t> as MessagePool;

    provides interface Compare<SeqNoWithAddr> as SeqNoWithAddrCompare;
	 
	uses interface Random;

	uses interface ParameterInit<uint16_t> as SeedInit;

	uses interface Crc;
}

implementation 
{

	SinkLocation sink_location = UnknownSinkLocation;
	BiasedType bias_direction = UnknownBiasType;

	WalkType messagetype = UnknownMessageType;
	WalkType nextmessagetype = UnknownMessageType;

	bool reach_borderline;

	hop_distance_t landmark_bottom_left_distance;
	hop_distance_t landmark_bottom_right_distance;
	hop_distance_t landmark_sink_distance;

	int16_t srw_count;	//short random walk count.
	int16_t lrw_count;	//long random walk count.

	hop_distance_t random_walk_hops;
	hop_distance_t long_random_walk_hops;

	distance_neighbours_t neighbours;

	uint32_t random_seed;

	bool busy = FALSE;
	message_t packet;

	// All node variables
	SequenceNumber normal_sequence_counter;
	SequenceNumber away_sequence_counter;

	uint32_t get_source_period()
	{
		assert(call NodeType.get() == SourceNode);
		return SOURCE_PERIOD_MS;
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

	void sink_location_check()
	{
		sink_location = (CONFIGURATION >= 1 && CONFIGURATION <= 3) ? Centre : Others ;
	}

	SetType random_walk_direction()
	{
		uint32_t possible_sets = UnknownSet;

		//simdbg("stdout", "call random_walk_direction, neighbours.size=%d\n", neighbours.size);

		if (sink_location == UnknownSinkLocation)
		{
			sink_location_check();
		}

		if (landmark_bottom_left_distance != UNKNOWN_HOP_DISTANCE && landmark_bottom_right_distance != UNKNOWN_HOP_DISTANCE)
		{
			uint32_t i;

			uint32_t FurtherSet_neighbours = 0;
			uint32_t CloserSideSet_neighbours = 0;
			uint32_t CloserSet_neighbours = 0;
			uint32_t FurtherSideSet_neighbours = 0;

			uint32_t count1 = 0;
			uint32_t count2 = 0;
			uint32_t count3 = 0;
			uint32_t count4 = 0;

			for (i = 0; i != neighbours.size; ++i)
			{

				distance_container_t const* const neighbour = &neighbours.data[i].contents;

				if (landmark_bottom_left_distance < neighbour->bottom_left_distance && landmark_bottom_right_distance <  neighbour->bottom_right_distance && count1 == 0)
				{
						FurtherSet_neighbours ++;
						FurtherSideSet_neighbours ++;
						count1 ++;
					
				}
				else if (landmark_bottom_left_distance > neighbour->bottom_left_distance && landmark_bottom_right_distance < neighbour->bottom_right_distance && count2 == 0)
				{
					CloserSideSet_neighbours ++;
					FurtherSet_neighbours ++;
					count2 ++;
				}
				else if (landmark_bottom_left_distance > neighbour->bottom_left_distance && landmark_bottom_right_distance >  neighbour->bottom_right_distance && count3 == 0)
				{
					CloserSet_neighbours ++;
					CloserSideSet_neighbours ++;
					count3 ++;				
				}
				else if (landmark_bottom_left_distance < neighbour->bottom_left_distance && landmark_bottom_right_distance > neighbour->bottom_right_distance && count4 == 0)
				{
					CloserSet_neighbours ++;
					FurtherSideSet_neighbours ++;
					count4 ++;
				}
				else
				{
					//simdbg("stdout", "Neighbour Divide Error!\n");
				}

				if (FurtherSideSet_neighbours > 1)
				{
					possible_sets |= FurtherSideSet;
				}

				if (CloserSideSet_neighbours > 1)
				{
					possible_sets |= CloserSideSet;
				}

				if (FurtherSet_neighbours > 1)
				{
					possible_sets |= FurtherSet; 
				}

				if (CloserSet_neighbours > 1)
				{
					possible_sets |= CloserSet;
				}
			}
			//simdbg("stdout", "[%d]:CloserSet_neighbours = %d, FurtherSet_neighbours = %d, CloserSideSet_neighbours = %d, FurtherSideSet_neighbours = %d\n",
			//		TOS_NODE_ID, CloserSet_neighbours, FurtherSet_neighbours, CloserSideSet_neighbours, FurtherSideSet_neighbours);
			//simdbg("stdout", "[NodeID:%d] sink_distance:%d, landmark_bottom_left_distance=%u, landmark_bottom_right_distance=%u\n", 
			//		TOS_NODE_ID, landmark_sink_distance, landmark_bottom_left_distance, landmark_bottom_right_distance);
		}

		if (possible_sets != UnknownSet)
		{
			uint16_t rnd = call Random.rand16() % bitcount(possible_sets) + 1;
			return (possible_sets >> rnd) + 1;
		}
		else
		{
			//do not retrun UnknownSet, because flooding sometimes is not relaiable
			if (sink_location == Centre)
			{
				return CloserSet;
			}
			else
			{
				return (call Random.rand16() % 2 == 0) ? CloserSideSet : FurtherSideSet;
			}
		}
	}


	am_addr_t random_walk_target(SetType further_or_closer_set, BiasedType biased_direction,
		                         const am_addr_t* to_ignore, size_t to_ignore_length)
	{
		am_addr_t chosen_address;
		uint32_t k;

		distance_neighbours_t local_neighbours;
		init_distance_neighbours(&local_neighbours);

		if (further_or_closer_set == UnknownSet)
			return AM_BROADCAST_ADDR;

		// If we don't know our sink distance then we cannot work
		// out which neighbour is in closer or further.
		if (landmark_bottom_left_distance != UNKNOWN_HOP_DISTANCE &&
			landmark_bottom_right_distance != UNKNOWN_HOP_DISTANCE &&
			further_or_closer_set != UnknownSet)
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
			//simdbgverbose("stdout", "No local neighbours to choose so broadcasting. (my-dist=%d, my-neighbours-size=%u)\n",
			//	landmark_bottom_left_distance, neighbours.size);
			chosen_address = AM_BROADCAST_ADDR;
		}
		else
		{
			distance_neighbour_detail_t*  neighbour;

			uint16_t rnd = call Random.rand16();
			uint16_t neighbour_index = rnd % local_neighbours.size;  //randomly choose neighbour index
			uint16_t brn = rnd % 100; 	//bias random number;

			if (sink_location == UnknownSinkLocation)
			{
				sink_location_check();
			}

			if (sink_location == Centre && further_or_closer_set == CloserSet)	//deal with biased random walk here.
			{
				//simdbg("stdout", "biased!\n");
				if (biased_direction == UnknownBiasType)
				{
					//simdbg("stdout", "UnknownBiasType!\n");
					neighbour = &local_neighbours.data[neighbour_index];   //choose one neighbour.

					//simdbg("stdout", "NodeID[%d]: landmark_bottom_left_distance=%d, neighbour->contents.bottom_left_distance=%d\n", 
					//		TOS_NODE_ID, landmark_bottom_left_distance, neighbour->contents.bottom_left_distance);

					if (landmark_bottom_left_distance > neighbour->contents.bottom_left_distance)
					{
						bias_direction = V;
					//	simdbg("stdout", "bias direction is V\n");
					}
					else if (landmark_bottom_left_distance < neighbour->contents.bottom_left_distance)
					{
						bias_direction = H;
					//	simdbg("stdout", "bias direction is H\n");
					}
					else
					{					
						//ranomly choose H or V
						bias_direction = (brn < 50)? V : H;
						//simdbgerror("stdout","bias_direction error!\n");
					}

					chosen_address = neighbour->address;

					//simdbg("stdout", "chosen address=%d\n", chosen_address);
				}
				else	
				{
					//bias_direction == H or bias_direction == V

					for (k = 0; k != local_neighbours.size; ++k)
					{
						neighbour = &local_neighbours.data[k];
						if(biased_direction == H)
						{
							if (landmark_bottom_left_distance <= neighbour->contents.bottom_left_distance && brn < BIASED_NO)
							{
								chosen_address = neighbour->address;
								break;
							}
						}
						else		//biased_direction is V
						{
							if (landmark_bottom_left_distance >= neighbour->contents.bottom_left_distance && brn < BIASED_NO)
							{
								chosen_address = neighbour->address;
								break;
							}
						}
						chosen_address = neighbour->address;
					}
				}
			}
			else
			{
				//normal case.
				//simdbg("stdout", "normal case, sink_location type:%d, further_or_closer_set:%d\n", sink_location, further_or_closer_set);
				if(local_neighbours.size == 1 && further_or_closer_set != CloserSet)
				{
					//simdbg("stdout", "set reach_borderline to TRUE!\n");
					reach_borderline = TRUE;
				}
				else
				{
					neighbour = &local_neighbours.data[neighbour_index];
					chosen_address = neighbour->address;
				}
			}
		}
		//print_distance_neighbours("stdout", &local_neighbours);

		//simdbgverbose("stdout", "Location:%u, biased_direction:%u, Chosen %u at index %u (rnd=%u) out of %u neighbours\n",
		//		sink_location, biased_direction, chosen_address, neighbour_index, rnd, local_neighbours.size);

		//simdbg("stdout", "chosen_address = %d\n", chosen_address);
		return chosen_address;
	}

	int16_t short_long_sequence_random_walk(int16_t short_count, int16_t long_count)
	{
		int16_t rw;
		if (short_count != 0)
		{	
			rw = random_walk_hops;
			srw_count -= 1;
		}
		else
		{
			rw = long_random_walk_hops;
			lrw_count -= 1;
		}
		return rw;
	}

	int16_t long_short_sequence_random_walk(int16_t short_count, int16_t long_count)
	{
		int16_t rw;
		if (long_count != 0)
		{
			rw = long_random_walk_hops;
			lrw_count -= 1;
		}
		else
		{
			rw = random_walk_hops;
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

	USE_MESSAGE_ACK_REQUEST_WITH_CALLBACK(Normal);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Away);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Beacon);

	bool has_enough_messages_to_send(void)
	{
		return call MessageQueue.count() > 0;
	}

	message_queue_info_t* choose_message_to_send(void)
	{
		message_queue_info_t** const begin = call MessageQueue.begin();

		if (call MessageQueue.count() == 0)
		{
			return NULL;
		}

		return begin[0];
	}

	void put_back_in_pool(message_queue_info_t* info)
	{
		const NormalMessage* const rcvd = (NormalMessage*)call NormalSend.getPayload(&info->msg, sizeof(NormalMessage));

		const SeqNoWithAddr seq_no_lookup = {rcvd->sequence_number, rcvd->source_id};

		call MessageQueue.remove(seq_no_lookup);
		call MessagePool.put(info);
	}

	message_queue_info_t* find_message_queue_info(message_t* msg)
	{
		const NormalMessage* const rcvd = (NormalMessage*)call NormalSend.getPayload(msg, sizeof(NormalMessage));

		const SeqNoWithAddr seq_no_lookup = {rcvd->sequence_number, rcvd->source_id};

		return call MessageQueue.get_or_default(seq_no_lookup, NULL);
	}

	error_t record_received_message(message_t* msg)
	{
		//bool success;
		message_queue_info_t* item;

		// Check if there is already a message with this sequence number present
		// If there is then we will just overwrite it with the current message.
		item = find_message_queue_info(msg);

		if (!item)
		{
			bool success;
			SeqNoWithAddr seq_no_lookup;
			const NormalMessage* rcvd = (NormalMessage*)call NormalSend.getPayload(msg, sizeof(NormalMessage));

			if (!rcvd)
			{
				return FAIL;
			}

			//simdbg("stdout","bd: %d\n", rcvd->biased_direction);

			item = call MessagePool.get();
			if (!item)
			{
				ERROR_OCCURRED(ERROR_POOL_FULL, "No pool space available for another message.\n");
				return ENOMEM;
			}

			seq_no_lookup.seq_no = rcvd->sequence_number;
			seq_no_lookup.addr = rcvd->source_id;

			success = call MessageQueue.put(seq_no_lookup, item);
			if (!success)
			{
				ERROR_OCCURRED(ERROR_QUEUE_FULL, "No queue space available for another message.\n");

				call MessagePool.put(item);

				return ENOMEM;
			}
		}
		else
		{
			simdbgverbose("stdout", "Overwriting message in the queue with a message of the same seq no and source id\n");
		}

		item->msg = *msg;

		item->time_added = call LocalTime.get();
		item->ack_requested = FALSE;
		item->rtx_attempts = RTX_ATTEMPTS;

		if (has_enough_messages_to_send())
		{
			call ConsiderTimer.startOneShot(ALPHA);
		}

		return SUCCESS;
	}

	void send_Normal_done(message_t* msg, error_t error)
	{
		if (error != SUCCESS)
		{
			// Failed to send the message
			//simdbg("stdout", "failed to send a message!\n");
			call ConsiderTimer.startOneShot(ALPHA_RETRY);
		}
		else
		{
			message_queue_info_t* const info = find_message_queue_info(msg);

			if (info != NULL)
			{
				NormalMessage* const normal_message = (NormalMessage*)call NormalSend.getPayload(&info->msg, sizeof(NormalMessage));

				const bool ack_requested = info->ack_requested;
				const bool was_acked = call NormalPacketAcknowledgements.wasAcked(msg);

				if (ack_requested & !was_acked)
				{
					// Message was sent, but no ack received
					// Leaving the message in the queue will cause it to be sent again
					// in the next consider slot.
					info->rtx_attempts -= 1;

					// Give up sending this message
					if (info->rtx_attempts == 0)
					{
						
						//ERROR_OCCURRED(ERROR_RTX_FAILED,
						//	"Failed to send message " NXSEQUENCE_NUMBER_SPEC ".\n",
						//	normal_message->sequence_number);

						// Failed to route to sink, so remove from queue.
						put_back_in_pool(info);

						// If we have more messages to send, lets queue them up!
						if (has_enough_messages_to_send())
						{
							call ConsiderTimer.startOneShot(ALPHA_RETRY);
						}						
					}
					else
					{
						// resend the message again.
						call ConsiderTimer.startOneShot(ALPHA);
					}
				}
				else
				{
					// All good
					put_back_in_pool(info);

					if (has_enough_messages_to_send())
					{
						call ConsiderTimer.startOneShot(ALPHA_RETRY);
					}
				}
			}
			else
			{
				const NormalMessage* const normal_message = (NormalMessage*)call NormalSend.getPayload(msg, sizeof(NormalMessage));

				ERROR_OCCURRED(ERROR_DICTIONARY_KEY_NOT_FOUND, "Unable to find the dict key (%" PRIu32 ", %" PRIu16 ") for the message\n",
					normal_message->sequence_number, normal_message->source_id);
#ifdef SLP_VERBOSE_DEBUG				
				print_dictionary_queue();
#endif
			}
		}
	}

	event void ConsiderTimer.fired()
	{
		if (has_enough_messages_to_send())
		{
			message_queue_info_t* const info = choose_message_to_send();
			NormalMessage* info_msg;
			NormalMessage forwarding_message;
			am_addr_t source_addr;

			if (info == NULL)
			{
				return;
			}

			info_msg = (NormalMessage*)call NormalSend.getPayload(&info->msg, sizeof(NormalMessage));
			source_addr = info_msg->source_id;

			forwarding_message = *info_msg;
			forwarding_message.source_distance += 1;
			
			forwarding_message.landmark_distance_of_bottom_left_sender = landmark_bottom_left_distance;
			forwarding_message.landmark_distance_of_bottom_right_sender = landmark_bottom_right_distance;
			forwarding_message.landmark_distance_of_sink_sender = landmark_sink_distance;

			if (info_msg->source_distance + 1 < info_msg->random_walk_hops && !info_msg->broadcast)
			{
				am_addr_t target;

				if (forwarding_message.further_or_closer_set == UnknownSet)
				{
					forwarding_message.further_or_closer_set = random_walk_direction();
				}

				if (TOS_NODE_ID == source_addr)
				{
					target = random_walk_target(forwarding_message.further_or_closer_set, UnknownBiasType, NULL, 0);
					forwarding_message.biased_direction = bias_direction;
					//simdbg("stdout", "bd = %d\n", forwarding_message.biased_direction);
				}			
				else
				{
					target = random_walk_target(forwarding_message.further_or_closer_set, forwarding_message.biased_direction, &source_addr, 1);
					if (reach_borderline == TRUE && forwarding_message.further_or_closer_set != CloserSet)
					{
						//simdbg("stdout", "reach_borderline!\n");
						forwarding_message.further_or_closer_set = CloserSet;
						target = random_walk_target(forwarding_message.further_or_closer_set, forwarding_message.biased_direction, &source_addr, 1);
					}
					//simdbg("stdout", "[%d]::forwarding_message.biased_direction =%d\n", TOS_NODE_ID, forwarding_message.biased_direction);
					//target = random_walk_target(forwarding_message.further_or_closer_set, forwarding_message.biased_direction, &source_addr, 1);
					//simdbg("stdout", "choose the target %d\n", target);
				}

				if (target == AM_BROADCAST_ADDR)
				{
					return;
				}

				forwarding_message.broadcast = (target == AM_BROADCAST_ADDR);


				//simdbg("stdout", "[Message SeqNo: %d]: Forwarding normal from %d to target = %d\n",
				//		forwarding_message.sequence_number, TOS_NODE_ID, target);

				call Packet.clear(&packet);

				info->ack_requested = (target != AM_BROADCAST_ADDR && info->rtx_attempts > 0);

				send_Normal_message(&forwarding_message, target, &info->ack_requested);
			}
			else
			//broadcast messages
			{
				if (!info_msg->broadcast || (info_msg->source_distance + 1 == info_msg->random_walk_hops))
				{
					//simdbgverbose("M-PE", TOS_NODE_ID_SPEC "," TOS_NODE_ID_SPEC "," NXSEQUENCE_NUMBER_SPEC ",%u\n",
					//	source_addr, info_msg->source_id, info_msg->sequence_number, info_msg->source_distance + 1);
				}

				// We want other nodes to continue broadcasting
				forwarding_message.broadcast = TRUE;

				//info->ack_requested = (forwarding_message.broadcast == TRUE && info->rtx_attempts > 0);
				info->ack_requested = FALSE;

				//simdbg("stdout", "Message source distance: %d. Broadcasting!\n", info_msg->source_distance);

				call Packet.clear(&packet);

				send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR, &info->ack_requested);
			}
		}
	}

	event void Boot.booted()
	{
		reach_borderline = FALSE;

		landmark_bottom_left_distance = UNKNOWN_HOP_DISTANCE;
		landmark_bottom_right_distance = UNKNOWN_HOP_DISTANCE;
		landmark_sink_distance = UNKNOWN_HOP_DISTANCE;

		srw_count = 0;	//short random walk count.
		lrw_count = 0;	//long random walk count.

		random_walk_hops = UNKNOWN_HOP_DISTANCE;
		long_random_walk_hops = UNKNOWN_HOP_DISTANCE;

		busy = FALSE;

		init_distance_neighbours(&neighbours);

		sequence_number_init(&normal_sequence_counter);
		sequence_number_init(&away_sequence_counter);

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

		random_seed = (uint32_t)sim_time();
		call SeedInit.init(random_seed);

		call RadioControl.start();
	}

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			simdbgverbose("SourceBroadcasterC", "RadioControl started.\n");

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
		}
		else
		{
			ERROR_OCCURRED(ERROR_RADIO_CONTROL_START_FAIL, "RadioControl failed to start, retrying.\n");

			call RadioControl.start();
		}
	}

	event void RadioControl.stopDone(error_t err)
	{
		simdbgverbose("SourceBroadcasterC", "RadioControl stopped.\n");
	}

	event void ObjectDetector.detect()
	{
		// A sink node cannot become a source node
		if (call NodeType.get() != SinkNode)
		{
			call NodeType.set(SourceNode);

			call BroadcastNormalTimer.startOneShot(7 * 1000);	//wait till beacon messages send finished.
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
		message.source_id = TOS_NODE_ID;
		message.landmark_distance = 0;

		message.sequence_number = call AwaySeqNos.next(TOS_NODE_ID);

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
		message.source_id = TOS_NODE_ID;
		message.landmark_distance = 0;

		message.sequence_number = call AwaySeqNos.next(TOS_NODE_ID);

		call Packet.clear(&packet);

		if (send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			call AwaySeqNos.increment(TOS_NODE_ID);
		}
	}

	event void BroadcastNormalTimer.fired()
	{
		message_t msg;
		NormalMessage* message;
		am_addr_t target;
		uint16_t half_ssd;
		const uint32_t source_period = get_source_period();

		//print_distance_neighbours("stdout", &neighbours);

		call Packet.clear(&msg);
		// Need to set source as we do not go through the send interface
		call AMPacket.setSource(&msg, TOS_NODE_ID);

		message = (NormalMessage*)call NormalSend.getPayload(&msg, sizeof(NormalMessage));

		//simdbg("stdout", "%s: BroadcastNormalTimer fired.\n", sim_time_string());

		//initialise the short sount and long count.
		if (srw_count == 0 && lrw_count == 0)
		{
			srw_count = SHORT_COUNT;
			lrw_count = LONG_COUNT;
		}

		half_ssd = landmark_sink_distance / 2 -1;
		random_walk_hops = call Random.rand16() % half_ssd + 2;
		long_random_walk_hops = call Random.rand16() % half_ssd + landmark_sink_distance + 2;
				
		//simdbg("stdout","(ssd:%d,random walk length:%d)short random walk hop=%d, long random walk hop=%d\n", landmark_sink_distance, half_ssd, random_walk_hops, long_random_walk_hops);

		#ifdef SHORT_LONG_SEQUENCE
		{
			message->random_walk_hops = short_long_sequence_random_walk(srw_count, lrw_count);
			nextmessagetype = sl_next_message_type(srw_count, lrw_count);
		}
		#else
		{
			message->random_walk_hops = long_short_sequence_random_walk(srw_count, lrw_count);
			nextmessagetype = ls_next_message_type(srw_count, lrw_count);
		}
		#endif

		if (message->random_walk_hops == random_walk_hops)
		{
			messagetype = ShortRandomWalk;
		}
		else
		{
			messagetype = LongRandomWalk;
		}

		message->sequence_number = sequence_number_next(&normal_sequence_counter);
		message->source_id = TOS_NODE_ID;
		message->source_distance = 0;

		message->landmark_distance_of_bottom_left_sender = landmark_bottom_left_distance;
		message->landmark_distance_of_bottom_right_sender = landmark_bottom_right_distance;
		message->landmark_distance_of_sink_sender = landmark_sink_distance;		

		message->broadcast = FALSE;

		if (record_received_message(&msg) == SUCCESS)
		{
			sequence_number_increment(&normal_sequence_counter);
		}
		else
		{
			simdbgverbose("stdout", "record_received_message FAIL!\n");
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
			landmark_sink_distance = 0;
			message.landmark_location = SINK;
		}
		else
		{
			simdbgerror("stdout", "Error!\n");
		}
		message.sequence_number = sequence_number_next(&away_sequence_counter);
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

		message.landmark_distance_of_bottom_left_sender = landmark_bottom_left_distance;
		message.landmark_distance_of_bottom_right_sender = landmark_bottom_right_distance;
		message.landmark_distance_of_sink_sender = landmark_sink_distance;

		call Packet.clear(&packet);

		send_Beacon_message(&message, AM_BROADCAST_ADDR);
	}

	void Normal_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		const SeqNoWithAddr seq_no_lookup = {rcvd->sequence_number, rcvd->source_id};

		UPDATE_LANDMARK_DISTANCE_BL(rcvd, landmark_distance_of_bottom_left_sender);
		UPDATE_LANDMARK_DISTANCE_BR(rcvd, landmark_distance_of_bottom_right_sender);
		UPDATE_LANDMARK_DISTANCE_SINK(rcvd, landmark_distance_of_sink_sender);
		
		UPDATE_NEIGHBOURS_BL(rcvd, source_addr, landmark_distance_of_bottom_left_sender);
		UPDATE_NEIGHBOURS_BR(rcvd, source_addr, landmark_distance_of_bottom_right_sender);		
		UPDATE_NEIGHBOURS_SINK(rcvd, source_addr, landmark_distance_of_sink_sender);

		if (!call LruNormalSeqNos.lookup(seq_no_lookup))
		{
			call LruNormalSeqNos.insert(seq_no_lookup);

			METRIC_RCV_NORMAL(rcvd);

			record_received_message(msg);
		}
	}

	void Sink_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		const SeqNoWithAddr seq_no_lookup = {rcvd->sequence_number, rcvd->source_id};

		UPDATE_LANDMARK_DISTANCE_BL(rcvd, landmark_distance_of_bottom_left_sender);
		UPDATE_LANDMARK_DISTANCE_BR(rcvd, landmark_distance_of_bottom_right_sender);
		UPDATE_LANDMARK_DISTANCE_SINK(rcvd, landmark_distance_of_sink_sender);
		
		UPDATE_NEIGHBOURS_BL(rcvd, source_addr, landmark_distance_of_bottom_left_sender);
		UPDATE_NEIGHBOURS_BR(rcvd, source_addr, landmark_distance_of_bottom_right_sender);		
		UPDATE_NEIGHBOURS_SINK(rcvd, source_addr, landmark_distance_of_sink_sender);

		if (!call LruNormalSeqNos.lookup(seq_no_lookup))
		{
			call LruNormalSeqNos.insert(seq_no_lookup);

			METRIC_RCV_NORMAL(rcvd);

			record_received_message(msg);
		}
	}

	void Source_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS_BL(rcvd, source_addr, landmark_distance_of_bottom_left_sender);
		UPDATE_NEIGHBOURS_BR(rcvd, source_addr, landmark_distance_of_bottom_right_sender);
		UPDATE_NEIGHBOURS_SINK(rcvd, source_addr, landmark_distance_of_sink_sender);

		UPDATE_LANDMARK_DISTANCE_BL(rcvd, landmark_distance_of_bottom_left_sender);
		UPDATE_LANDMARK_DISTANCE_BR(rcvd, landmark_distance_of_bottom_right_sender);
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
		UPDATE_NEIGHBOURS_SINK(rcvd, source_addr, landmark_distance_of_sink_sender);

		UPDATE_LANDMARK_DISTANCE_BL(rcvd, landmark_distance_of_bottom_left_sender);
		UPDATE_LANDMARK_DISTANCE_BR(rcvd, landmark_distance_of_bottom_right_sender);
		UPDATE_LANDMARK_DISTANCE_SINK(rcvd, landmark_distance_of_sink_sender);
	}

	void x_snoop_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS_BL(rcvd, source_addr, landmark_distance_of_bottom_left_sender);
		UPDATE_NEIGHBOURS_BR(rcvd, source_addr, landmark_distance_of_bottom_right_sender);
		UPDATE_NEIGHBOURS_SINK(rcvd, source_addr, landmark_distance_of_sink_sender);

		UPDATE_LANDMARK_DISTANCE_BL(rcvd, landmark_distance_of_bottom_left_sender);
		UPDATE_LANDMARK_DISTANCE_BR(rcvd, landmark_distance_of_bottom_right_sender);
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
			UPDATE_NEIGHBOURS_BL(rcvd, source_addr, landmark_distance);
			UPDATE_LANDMARK_DISTANCE_BL(rcvd, landmark_distance);
		}
		if (rcvd->landmark_location == BOTTOMRIGHT)
		{
			UPDATE_NEIGHBOURS_BR(rcvd, source_addr, landmark_distance);
			UPDATE_LANDMARK_DISTANCE_BR(rcvd, landmark_distance);
		}
		if (rcvd->landmark_location == SINK)
		{
			UPDATE_NEIGHBOURS_SINK(rcvd, source_addr, landmark_distance);
			UPDATE_LANDMARK_DISTANCE_SINK(rcvd, landmark_distance);
		}

		if (call AwaySeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			call AwaySeqNos.update(rcvd->source_id, rcvd->sequence_number);
			
			METRIC_RCV_AWAY(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.landmark_distance += 1;

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

		UPDATE_NEIGHBOURS_SINK(rcvd, source_addr, landmark_distance_of_sink_sender);
		UPDATE_LANDMARK_DISTANCE_SINK(rcvd, landmark_distance_of_sink_sender);

		METRIC_RCV_BEACON(rcvd);
	}

	RECEIVE_MESSAGE_BEGIN(Beacon, Receive)
		case NormalNode:
		case SourceNode:
		case SinkNode: x_receieve_Beacon(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Beacon)

	command bool SeqNoWithAddrCompare.equals(const SeqNoWithAddr* a, const SeqNoWithAddr* b)
	{
		return a->seq_no == b->seq_no && a->addr == b->addr;
	}
}