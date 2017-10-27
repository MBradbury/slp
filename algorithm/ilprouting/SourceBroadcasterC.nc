#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"
#include "HopDistance.h"

#include "NeighbourDetail.h"

#include "MessageQueueInfo.h"
#include "SeqNoWithFlag.h"

#include "NormalMessage.h"
#include "AwayMessage.h"
#include "BeaconMessage.h"
#include "PollMessage.h"

#include <Timer.h>
#include <TinyError.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, msg->sink_distance + 1)
#define METRIC_RCV_BEACON(msg) METRIC_RCV(Beacon, source_addr, BOTTOM, UNKNOWN_SEQNO, UNKNOWN_HOP_DISTANCE)
#define METRIC_RCV_POLL(msg) METRIC_RCV(Poll, source_addr, BOTTOM, UNKNOWN_SEQNO, UNKNOWN_HOP_DISTANCE)

void ni_update(ni_container_t* find, ni_container_t const* given)
{
	find->sink_distance = hop_distance_min(find->sink_distance, given->sink_distance);
	find->source_distance = hop_distance_min(find->source_distance, given->source_distance);
	find->backtracks_from += given->backtracks_from;
}

void ni_print(const char* name, size_t i, am_addr_t address, ni_container_t const* contents)
{
	simdbg_clear(name, "(%zu) %u: sink-dist=%d src-dist=%d",
		i, address, contents->sink_distance, contents->source_distance);
}

DEFINE_NEIGHBOUR_DETAIL(ni_container_t, ni, ni_update, ni_print, SLP_MAX_1_HOP_NEIGHBOURHOOD);

#define UPDATE_NEIGHBOURS(source_addr, sink_distance, source_distance, backtracks_from) \
{ \
	const ni_container_t dist = { sink_distance, source_distance, backtracks_from }; \
	call Neighbours.record(source_addr, &dist); \
}

#define CHOOSE_NEIGHBOURS_WITH_PREDICATE(PRED) \
if (local_neighbours.size == 0) \
{ \
	const am_addr_t* iter; \
	const am_addr_t* end; \
	for (iter = call Neighbours.beginKeys(), end = call Neighbours.endKeys(); iter != end; ++iter) \
	{ \
		const am_addr_t address = *iter; \
		ni_container_t const* const neighbour = call Neighbours.get_from_iter(iter); \
 \
		if (PRED) \
		{ \
			insert_ni_neighbour(&local_neighbours, address, neighbour); \
		} \
	} \
}

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;
	uses interface Random;

	uses interface Timer<TMilli> as ConsiderTimer;
	uses interface Timer<TMilli> as AwaySenderTimer;

	uses interface Packet;
	uses interface AMPacket;

	uses interface SplitControl as RadioControl;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;
	uses interface Receive as NormalSnoop;
	uses interface PacketAcknowledgements as NormalPacketAcknowledgements;

	uses interface AMSend as AwaySend;
	uses interface Receive as AwayReceive;

	uses interface MetricLogging;
	uses interface MetricHelpers;

	uses interface NodeType;
	uses interface MessageType;
	uses interface ObjectDetector;
	uses interface SourcePeriodModel;

	uses interface Cache<SeqNoWithFlag> as LruNormalSeqNos;

	uses interface LocalTime<TMilli>;

	uses interface Neighbours<ni_container_t, BeaconMessage, PollMessage>;

	// Messages that are queued to send
	uses interface Dictionary<SeqNoWithAddr, message_queue_info_t*> as MessageQueue;
    uses interface Pool<message_queue_info_t> as MessagePool;

    provides interface Compare<SeqNoWithAddr> as SeqNoWithAddrCompare;
    provides interface Compare<SeqNoWithFlag> as SeqNoWithFlagCompare;

#ifdef LOW_POWER_LISTENING
	uses interface LowPowerListening;

	uses interface Timer<TMilli> as StartDutyCycleTimer;
#endif
}

implementation
{
	#include "HopDistanceDebug.h"

	bool busy;
	message_t packet;

	// All node variables
	SequenceNumber normal_sequence_counter;
	SequenceNumber away_sequence_counter;

	hop_distance_t sink_distance;
	hop_distance_t source_distance;
	hop_distance_t sink_source_distance;

	am_addr_t previously_sent_to;

	// Source variables
	int8_t current_message_grouping;

	// Sink variables
	int sink_away_messages_to_send;

	// Rest

	// Produces a random float between 0 and 1
	float random_float(void)
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

	event void Boot.booted()
	{
		METRIC_BOOT();

		busy = FALSE;
		sink_distance = UNKNOWN_HOP_DISTANCE;
		source_distance = UNKNOWN_HOP_DISTANCE;
		sink_source_distance = UNKNOWN_HOP_DISTANCE;

		previously_sent_to = AM_BROADCAST_ADDR;

		current_message_grouping = BOTTOM;

		call Packet.clear(&packet);

		sequence_number_init(&normal_sequence_counter);
		sequence_number_init(&away_sequence_counter);

		sink_away_messages_to_send = SINK_AWAY_MESSAGES_TO_SEND;

		call MessageType.register_pair(NORMAL_CHANNEL, "Normal");
		call MessageType.register_pair(AWAY_CHANNEL, "Away");
		call MessageType.register_pair(BEACON_CHANNEL, "Beacon");
		call MessageType.register_pair(POLL_CHANNEL, "Poll");

		call NodeType.register_pair(SourceNode, "SourceNode");
		call NodeType.register_pair(SinkNode, "SinkNode");
		call NodeType.register_pair(NormalNode, "NormalNode");

		// All nodes should listen continuously during setup phase
#ifdef LOW_POWER_LISTENING
		call LowPowerListening.setLocalWakeupInterval(0);
#endif

		if (call NodeType.is_node_sink())
		{
			call NodeType.init(SinkNode);

			sink_distance = 0;
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

			call ObjectDetector.start_later(SLP_OBJECT_DETECTOR_START_DELAY_MS);

			if (call NodeType.get() == SinkNode)
			{
				call AwaySenderTimer.startOneShot(SINK_AWAY_DELAY_MS);
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

			call SourcePeriodModel.startPeriodic();

			source_distance = 0;
			sink_source_distance = sink_distance;

			current_message_grouping = (SLP_MESSAGE_GROUP_SIZE - 1);
		}
	}

	event void ObjectDetector.stoppedDetecting()
	{
		if (call NodeType.get() == SourceNode)
		{
			call SourcePeriodModel.stop();

			call NodeType.set(NormalNode);

			source_distance = UNKNOWN_HOP_DISTANCE;
			sink_source_distance = UNKNOWN_HOP_DISTANCE;
		}
	}

#ifdef LOW_POWER_LISTENING
	event void StartDutyCycleTimer.fired()
	{
		// The sink does not do duty cycling and keeps its radio on at all times
		if (call NodeType.get() == SinkNode)
		{
			return;
		}
		
		call LowPowerListening.setLocalWakeupInterval(LPL_DEF_LOCAL_WAKEUP);
	}
#endif

	USE_MESSAGE_ACK_REQUEST_WITH_CALLBACK(Normal);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Away);

#ifdef SLP_VERBOSE_DEBUG
	void print_dictionary_queue(void)
	{
		const SeqNoWithAddr* begin = call MessageQueue.beginKeys();
		const SeqNoWithAddr* end = call MessageQueue.endKeys();

		simdbg("stdout", "{");

		for (; begin != end; ++begin)
		{
			const SeqNoWithAddr key = *begin;
			message_queue_info_t** value = call MessageQueue.get(key);

			if (value)
			{
				simdbg_clear("stdout", "(" NXSEQUENCE_NUMBER_SPEC "," TOS_NODE_ID_SPEC "): %p", key.seq_no, key.addr, *value);
			}
			else
			{
				simdbg_clear("stdout", "(" NXSEQUENCE_NUMBER_SPEC "," TOS_NODE_ID_SPEC "): NULL", key.seq_no, key.addr);
			}

			if (begin + 1 != end)
			{
				simdbg_clear("stdout", ", ");
			}
		}

		simdbg_clear("stdout", "}\n");
	}

	void print_neighbours(void)
	{
		const am_addr_t* begin = call Neighbours.beginKeys();
		const am_addr_t* end = call Neighbours.endKeys();

		simdbg("stdout", "{");

		for (; begin != end; ++begin)
		{
			const am_addr_t key = *begin;
			ni_container_t const* const value = call Neighbours.get_from_iter(begin);

			simdbg_clear("stdout", TOS_NODE_ID_SPEC ": (dsrc=%d, dsink=%d)",
				key, value->source_distance, value->sink_distance);

			if (begin + 1 != end)
			{
				simdbg_clear("stdout", ", ");
			}
		}

		simdbg_clear("stdout", "}\n");
	}
#endif

	bool has_enough_messages_to_send(void)
	{
		return call MessageQueue.count() > 0;
	}

	message_queue_info_t* choose_message_to_send(void)
	{
		message_queue_info_t** const begin = call MessageQueue.begin();

		// Cannot choose messages to send when there are no messages
		if (call MessageQueue.count() == 0)
		{
			return NULL;
		}

		return begin[0];
	}

	bool source_should_send_to_sink(void)
	{
		// Wait for a few messages to head out before doing this.

		if (sequence_number_get(&normal_sequence_counter) <= 10)
		{
			return FALSE;
		}

		return random_float() <= SLP_PR_SEND_DIRECT_TO_SINK;
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

	error_t record_received_message(message_t* msg, uint8_t switch_stage)
	{
		message_queue_info_t* item;
		NormalMessage* stored_normal_message;

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
				ERROR_OCCURRED(ERROR_PACKET_HAS_NO_PAYLOAD, "In record_received_message: Packet has no payload.\n");
				return FAIL;
			}

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

		memcpy(&item->msg, msg, sizeof(*msg));

		stored_normal_message = (NormalMessage*)call NormalSend.getPayload(&item->msg, sizeof(NormalMessage));

		if (switch_stage != UINT8_MAX)
		{
			stored_normal_message->stage = switch_stage;
		}

		item->time_added = call LocalTime.get();
		item->proximate_source = call AMPacket.source(msg);
		item->ack_requested = FALSE;
		item->rtx_attempts = RTX_ATTEMPTS;
		item->calculate_target_attempts = CALCULATE_TARGET_ATTEMPTS;

		if (has_enough_messages_to_send())
		{
			// TODO: Look at a way to choose to_delay when sink_source_distance == BOTTOM
			const uint16_t to_delay = (stored_normal_message->source_distance < sink_source_distance)
				? stored_normal_message->delay
				: ALPHA;

			call ConsiderTimer.startOneShot(to_delay);
		}

		return SUCCESS;
	}

	void send_Normal_done(message_t* msg, error_t error)
	{
		if (error != SUCCESS)
		{
			// Failed to send the message
			call ConsiderTimer.startOneShot(ALPHA_RETRY);
		}
		else
		{
			message_queue_info_t* const info = find_message_queue_info(msg);

			if (info != NULL)
			{
				NormalMessage* const normal_message = (NormalMessage*)call NormalSend.getPayload(&info->msg, sizeof(NormalMessage));

				const am_addr_t target = call AMPacket.destination(msg);

				const bool ack_requested = info->ack_requested;
				const bool was_acked = call NormalPacketAcknowledgements.wasAcked(msg);

				if (ack_requested & !was_acked)
				{
					// Message was sent, but no ack received
					// Leaving the message in the queue will cause it to be sent again
					// in the next consider slot.

					call Neighbours.rtx_result(target, FALSE);

					info->failed_neighbour_sends[failed_neighbour_sends_length(info)] = target;

					info->rtx_attempts -= 1;

					// When we hit this threshold, send out a query message asking for
					// neighbours to identify themselves.
					if (info->rtx_attempts == BAD_NEIGHBOUR_DO_SEARCH_THRESHOLD)
					{
						PollMessage message;
						message.sink_distance_of_sender = sink_distance;
						message.source_distance_of_sender = source_distance;

						simdbg("stdout", "RTX failed several times, sending poll (dsink=%d, dsrc=%d)\n", sink_distance, source_distance);

						//print_ni_neighbours("stdout", &neighbours);

						call Neighbours.poll(&message);
					}

					// Give up sending this message
					if (info->rtx_attempts == 0)
					{
						if (normal_message->stage == NORMAL_ROUTE_AVOID_SINK)
						{
							// If we failed to route and avoid the sink, then lets just give up and route towards the sink
							normal_message->stage = NORMAL_ROUTE_TO_SINK;
							info->rtx_attempts = RTX_ATTEMPTS;

							ERROR_OCCURRED(ERROR_RTX_FAILED_TRYING_OTHER,
								"Failed to route message " NXSEQUENCE_NUMBER_SPEC " to avoid sink, giving up and routing to sink.\n",
								normal_message->sequence_number);

							call ConsiderTimer.startOneShot(ALPHA_RETRY);
						}
						else
						{
							ERROR_OCCURRED(ERROR_RTX_FAILED,
								"Failed to send message " NXSEQUENCE_NUMBER_SPEC " at stage %u.\n",
								normal_message->sequence_number, normal_message->stage);

							// Failed to route to sink, so remove from queue.
							put_back_in_pool(info);

							// If we have more messages to send, lets queue them up!
							if (has_enough_messages_to_send())
							{
								call ConsiderTimer.startOneShot(ALPHA_RETRY);
							}
						}
					}
					else
					{
						call ConsiderTimer.startOneShot(ALPHA * (RTX_ATTEMPTS - info->rtx_attempts));
					}
				}
				else
				{
					// All good
					put_back_in_pool(info);

					if (ack_requested & was_acked)
					{
						call Neighbours.rtx_result(target, TRUE);
					}

					previously_sent_to = target;

					// If we have more messages to send, lets queue them up!
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

//#ifdef SLP_VERBOSE_DEBUG
//				print_dictionary_queue();
//#endif
			}
		}
	}

	event void SourcePeriodModel.fired()
	{
		message_t msg;
		NormalMessage* message;

		simdbgverbose("stdout", "SourcePeriodModel fired.\n");

		call Packet.clear(&msg);

		// Need to set source as we do not go through the send interface
		call AMPacket.setSource(&msg, TOS_NODE_ID);

		message = (NormalMessage*)call NormalSend.getPayload(&msg, sizeof(NormalMessage));

		message->sequence_number = sequence_number_next(&normal_sequence_counter);
		message->source_distance = 0;
		message->sink_source_distance = sink_source_distance;
		message->source_id = TOS_NODE_ID;

		message->delay = ((current_message_grouping * call SourcePeriodModel.get()) + (sink_source_distance * ALPHA)) / sink_source_distance;

		simdbg("stdout", "Setting message delay of cg %u/%u to %u [ssd=%d]\n",
			current_message_grouping, (SLP_MESSAGE_GROUP_SIZE - 1), message->delay, sink_source_distance);

		// After a while we want to just route directly to the sink every so often.
		// This should improve the latency and also reduce the chances of avoidance messages
		// drawing the attacker back to the source.
		if (source_should_send_to_sink())
		{
			simdbgverbose("stdout", "source is sending message direct to the sink\n");
			message->stage = NORMAL_ROUTE_TO_SINK;
		}
		else
		{
			message->stage = NORMAL_ROUTE_AVOID_SINK;
		}

		// Put the message in the buffer, do not send directly.
		if (record_received_message(&msg, UINT8_MAX) == SUCCESS)
		{
			sequence_number_increment(&normal_sequence_counter);
		}

		if (current_message_grouping == 0)
		{
			current_message_grouping = (SLP_MESSAGE_GROUP_SIZE - 1);
		}
		else
		{
			current_message_grouping -= 1;
		}
	}

	ni_neighbour_detail_t* choose_random_neighbour(ni_neighbours_t* local_neighbours)
	{
		uint16_t rnd = call Random.rand16();
		uint16_t neighbour_index = rnd % local_neighbours->size;
		ni_neighbour_detail_t* neighbour = &local_neighbours->data[neighbour_index];

		// Try once more, to avoid always selecting the same target
		if (local_neighbours->size > 1 && neighbour->address == previously_sent_to)
		{
			rnd = call Random.rand16();
			neighbour_index = rnd % local_neighbours->size;
			neighbour = &local_neighbours->data[neighbour_index];
		}

		return neighbour;
	}

	void init_bad_neighbours(const message_queue_info_t* info, am_addr_t* bad_neighbours, uint8_t* bad_neighbours_size)
	{
		uint8_t i, j;

		am_addr_t skippable_neighbours[RTX_ATTEMPTS];
		uint8_t skippable_neighbours_count[RTX_ATTEMPTS];
		uint8_t skippable_neighbours_size = 0;

		// Count how many neighbours turn up
		for (i = 0; i != failed_neighbour_sends_length(info); ++i)
		{
			const am_addr_t bad_neighbour = info->failed_neighbour_sends[i];

			for (j = 0; j != skippable_neighbours_size; ++j)
			{
				if (skippable_neighbours[j] == bad_neighbour)
					break;
			}

			if (j == skippable_neighbours_size)
			{
				if (skippable_neighbours_size == RTX_ATTEMPTS)
				{
					ERROR_OCCURRED(ERROR_NO_MEMORY, "init_bad_neighbours internal buffer full\n");
				}
				else
				{
					skippable_neighbours_size += 1;

					skippable_neighbours[j] = bad_neighbour;
					skippable_neighbours_count[j] = 1;
				}
			}
			else
			{
				skippable_neighbours_count[j] += 1;
			}
		}

		// Copy neighbours that are bad to the list
		for (i = 0; i != skippable_neighbours_size; ++i)
		{
			if (skippable_neighbours_count[i] >= BAD_NEIGHBOUR_THRESHOLD)
			{
				if (*bad_neighbours_size == RTX_ATTEMPTS)
				{
					ERROR_OCCURRED(ERROR_NO_MEMORY, "init_bad_neighbours output buffer full\n");
					break;
				}

				bad_neighbours[*bad_neighbours_size] = skippable_neighbours[i];
				*bad_neighbours_size += 1;
			}
		}
	}

	bool neighbour_present(const am_addr_t* neighs, uint8_t neighs_size, am_addr_t neighbour)
	{
		uint8_t i;

		for (i = 0; i != neighs_size; ++i)
		{
			if (neighs[i] == neighbour)
			{
				return TRUE;
			}
		}

		return FALSE;
	}

	int16_t neighbour_source_distance(const ni_container_t * neighbour)
	{
		return neighbour->source_distance == UNKNOWN_HOP_DISTANCE
					? hop_distance_increment(source_distance)
					: neighbour->source_distance;
	}

	uint16_t lowest_backtracks_from_neighbours(void)
	{
		const am_addr_t* iter;
		const am_addr_t* end;

		uint16_t lowest = UINT16_MAX;

		for (iter = call Neighbours.beginKeys(), end = call Neighbours.endKeys(); iter != end; ++iter)
		{
			const am_addr_t address = *iter;
			ni_container_t const* const neighbour = call Neighbours.get_from_iter(iter);
	
			lowest = min(lowest, neighbour->backtracks_from);
		}

		return lowest;
	}

	bool find_next_in_avoid_sink_route(const message_queue_info_t* info, am_addr_t* next)
	{
		bool success = FALSE;

		const uint16_t lowest_num_backtracks = lowest_backtracks_from_neighbours();

		static const bool FT[] = {FALSE, TRUE};
		uint8_t i;

		am_addr_t bad_neighbours[RTX_ATTEMPTS];
		uint8_t bad_neighbours_size = 0;

		ni_neighbours_t local_neighbours;
		init_ni_neighbours(&local_neighbours);

		// Find out if there are any bad neighbours present. If there are
		// then we will try to pick a neighbour other than this one.
		init_bad_neighbours(info, bad_neighbours, &bad_neighbours_size);

		// Try to pick neighbours that have not been backtracked from first.
		// If we can't find any, then use the neighbour that has been backtracked from.
		for (i = 0; i != ARRAY_SIZE(FT); ++i)
		{
			// Prefer to pick neighbours with a greater source and also greater sink distance
			CHOOSE_NEIGHBOURS_WITH_PREDICATE(
				neighbour_source_distance(neighbour) > source_distance &&
				
				(neighbour->sink_distance != UNKNOWN_HOP_DISTANCE && sink_distance != UNKNOWN_HOP_DISTANCE &&
					neighbour->sink_distance >= sink_distance) &&

				(FT[i] || neighbour->backtracks_from == lowest_num_backtracks) &&

				address != info->proximate_source &&

				!neighbour_present(bad_neighbours, bad_neighbours_size, address)
			);

			// Otherwise look for neighbours with a greater source distance
			// that are in the ssd/2 area
			CHOOSE_NEIGHBOURS_WITH_PREDICATE(
				neighbour_source_distance(neighbour) > source_distance &&

				(sink_distance != UNKNOWN_HOP_DISTANCE && sink_source_distance != UNKNOWN_HOP_DISTANCE && sink_distance * 2 > sink_source_distance) &&

				(FT[i] || neighbour->backtracks_from == lowest_num_backtracks) &&

				address != info->proximate_source &&

				!neighbour_present(bad_neighbours, bad_neighbours_size, address)
			);
		}

		// If this is the source and the sink distance and ssd are unknown, just allow everyone.
		if (call NodeType.get() == SourceNode && (sink_distance == UNKNOWN_HOP_DISTANCE || sink_source_distance == UNKNOWN_HOP_DISTANCE))
		{
			CHOOSE_NEIGHBOURS_WITH_PREDICATE(TRUE);
		}

		if (local_neighbours.size > 0)
		{
			const ni_neighbour_detail_t* const neighbour = choose_random_neighbour(&local_neighbours);

			*next = neighbour->address;
			success = TRUE;
		}

		return success;
	}

	bool find_next_in_avoid_sink_backtrack_route(const message_queue_info_t* info, am_addr_t* next)
	{
		// The normal message has hit a region where there are no suitable nodes
		// available. So the message will need to go closer to the source to look
		// for a better route.

		bool success = FALSE;

		ni_neighbours_t local_neighbours;
		init_ni_neighbours(&local_neighbours);

		CHOOSE_NEIGHBOURS_WITH_PREDICATE(
			// Do not send back to the previous node
			address != info->proximate_source &&

			(neighbour->sink_distance == UNKNOWN_HOP_DISTANCE || neighbour->sink_distance >= sink_distance)
		);

		if (local_neighbours.size > 0)
		{
			const ni_neighbour_detail_t* const neighbour = choose_random_neighbour(&local_neighbours);

			*next = neighbour->address;
			success = TRUE;
		}

		return success;
	}

	bool find_next_in_to_sink_route(const message_queue_info_t* info, am_addr_t* next)
	{
		// Want to find a neighbour who has a smaller sink distance

		bool success = FALSE;

		am_addr_t bad_neighbours[RTX_ATTEMPTS];
		uint8_t bad_neighbours_size = 0;

		ni_neighbours_t local_neighbours;
		init_ni_neighbours(&local_neighbours);

		// Find out if there are any bad neighbours present. If there are
		// then we will try to pick a neighbour other than this one.
		init_bad_neighbours(info, bad_neighbours, &bad_neighbours_size);

		// Try sending to neighbours that are closer to the sink and further from the source
		CHOOSE_NEIGHBOURS_WITH_PREDICATE(
			neighbour->sink_distance != UNKNOWN_HOP_DISTANCE && sink_distance != UNKNOWN_HOP_DISTANCE &&
			neighbour->sink_distance < sink_distance &&

			neighbour->source_distance != UNKNOWN_HOP_DISTANCE && source_distance != UNKNOWN_HOP_DISTANCE &&
			neighbour->source_distance >= source_distance &&

			!neighbour_present(bad_neighbours, bad_neighbours_size, address)
		);

		// Try sending to neighbours closer to the sink
		CHOOSE_NEIGHBOURS_WITH_PREDICATE(
			neighbour->sink_distance != UNKNOWN_HOP_DISTANCE && sink_distance != UNKNOWN_HOP_DISTANCE &&
			neighbour->sink_distance < sink_distance &&

			!neighbour_present(bad_neighbours, bad_neighbours_size, address)
		);

		// Try sliding about same-sink distance nodes
		CHOOSE_NEIGHBOURS_WITH_PREDICATE(
			neighbour->sink_distance != UNKNOWN_HOP_DISTANCE && sink_distance != UNKNOWN_HOP_DISTANCE &&
			neighbour->sink_distance == sink_distance &&

			!neighbour_present(bad_neighbours, bad_neighbours_size, address)
		);

		// Just pick a random neighbour that wasn't the one we just came from
		CHOOSE_NEIGHBOURS_WITH_PREDICATE(
			address != info->proximate_source &&

			!neighbour_present(bad_neighbours, bad_neighbours_size, address)
		);

		// Pick any neighbour
		CHOOSE_NEIGHBOURS_WITH_PREDICATE(TRUE);

		if (local_neighbours.size > 0)
		{
			const ni_neighbour_detail_t* const neighbour = choose_random_neighbour(&local_neighbours);

			*next = neighbour->address;
			success = TRUE;
		}

		return success;
	}

	bool find_next_in_from_sink_route(const message_queue_info_t* info, am_addr_t* next)
	{
		bool success = FALSE;

		ni_neighbours_t local_neighbours;
		init_ni_neighbours(&local_neighbours);

		// The sink should broadcast to all neighbours
		// Subsequent nodes should unicast, but might broadcast
		if (call NodeType.get() == SinkNode)
		{
			*next = AM_BROADCAST_ADDR;
			return TRUE;
		}

		// Try to find nodes further from the sink
		CHOOSE_NEIGHBOURS_WITH_PREDICATE(
			// Do not send back to the previous node
			address != info->proximate_source &&

			neighbour->sink_distance > sink_distance
		);

		// Accept nodes that are the same sink distance away
		CHOOSE_NEIGHBOURS_WITH_PREDICATE(
			// Do not send back to the previous node
			address != info->proximate_source &&

			neighbour->sink_distance == sink_distance
		);

		if (local_neighbours.size == 0)
		{
			*next = AM_BROADCAST_ADDR;
			success = TRUE;
		}
		else
		{
			const ni_neighbour_detail_t* const neighbour = choose_random_neighbour(&local_neighbours);

			*next = neighbour->address;
			success = TRUE;
		}

		return success;
	}


	bool process_message(NormalMessage* message, message_queue_info_t* info, am_addr_t* next)
	{
		bool success = FALSE;

		// If we have hit the maximum walk distance, switch to routing to sink
		if (message->source_distance >= SLP_MAX_WALK_LENGTH)
		{
			message->stage = NORMAL_ROUTE_TO_SINK;

			simdbgverbose("stdout", "Switching to NORMAL_ROUTE_TO_SINK for " NXSEQUENCE_NUMBER_SPEC " as max walk length has been hit\n",
				message->sequence_number);
		}

		switch (message->stage)
		{
			case NORMAL_ROUTE_AVOID_SINK:
			{
				success = find_next_in_avoid_sink_route(info, next);

				simdbgverbose("stdout", "Found next for " NXSEQUENCE_NUMBER_SPEC " in avoid sink route with " TOS_NODE_ID_SPEC " ret %u\n",
					message->sequence_number, *next, success);

				if (!success)
				{
					if (sink_source_distance != UNKNOWN_HOP_DISTANCE && source_distance != UNKNOWN_HOP_DISTANCE && source_distance < sink_source_distance)
					{
						// We are too close to the source and it is likely that we haven't yet gone
						// around the sink. So lets try backtracking and finding another route.

						message->stage = NORMAL_ROUTE_AVOID_SINK_BACKTRACK;

						success = find_next_in_avoid_sink_backtrack_route(info, next);

						simdbg("stdout", "Switching from NORMAL_ROUTE_AVOID_SINK to NORMAL_ROUTE_AVOID_SINK_BACKTRACK chosen " TOS_NODE_ID_SPEC "\n", *next);
					}
					else
					{
						// When we are done with avoiding the sink, we need to head to it
						// No neighbours left to choose from, when far from the source

						message->stage = NORMAL_ROUTE_TO_SINK;

						success = find_next_in_to_sink_route(info, next);

						simdbg("stdout", "Switching from NORMAL_ROUTE_AVOID_SINK to NORMAL_ROUTE_TO_SINK chosen " TOS_NODE_ID_SPEC "\n", *next);
					}
				}
			} break;

			case NORMAL_ROUTE_AVOID_SINK_BACKTRACK:
			{
				// Received a message after backtracking, now need to pick a better direction to send it in.
				
				message->stage = NORMAL_ROUTE_AVOID_SINK;

				success = find_next_in_avoid_sink_route(info, next);

				simdbg("stdout", "Switching from NORMAL_ROUTE_AVOID_SINK_BACKTRACK to NORMAL_ROUTE_AVOID_SINK chosen %u\n", *next);

			} break;

			case NORMAL_ROUTE_TO_SINK:
			{
				success = find_next_in_to_sink_route(info, next);
			} break;

			case NORMAL_ROUTE_FROM_SINK:
			{
				// AM_BROADCAST_ADDR is valid for this function
				success = find_next_in_from_sink_route(info, next);
			} break;

			case NORMAL_ROUTE_AVOID_SINK_1_CLOSER:
			{
				// We want to avoid the sink in the future,
				// while allowing it to get 1 hop closer this time.
				
				message->stage = NORMAL_ROUTE_AVOID_SINK;

				success = find_next_in_to_sink_route(info, next);
			} break;

			default:
			{
				ERROR_OCCURRED(ERROR_UNKNOWN_MSG_STAGE, "Unknown message stage %" PRIu8 "\n", message->stage);
			} break;
		}

		return success;
	}

	task void consider_message_to_send()
	{
		am_addr_t next = AM_BROADCAST_ADDR;
		bool success = FALSE;

		message_queue_info_t* info;
		NormalMessage message;
		NormalMessage* info_msg;

		simdbgverbose("stdout", "ConsiderTimer fired. [MessageQueue.count()=%u]\n",
			call MessageQueue.count());

		// If we don't have any messages to send, then there is nothing to do
		if (!has_enough_messages_to_send())
		{
			LOG_STDOUT(ILPROUTING_NO_MESSAGES, "Unable to consider messages to send as we have no messages to send.\n");
			return;
		}

		// If we have no neighbour knowledge, then don't start sending
		if (call Neighbours.count() == 0)
		{
			ERROR_OCCURRED(ERROR_NO_NEIGHBOURS, "Unable to consider messages to send as we have no neighbours.\n");
			return;
		}

		info = choose_message_to_send();
		if (info == NULL)
		{
			ERROR_OCCURRED(ERROR_FAILED_CHOOSE_MSG, "Unable to choose a message to send (call MessageQueue.count()=%u).\n",
				call MessageQueue.count());
			return;
		}

		info_msg = (NormalMessage*)call NormalSend.getPayload(&info->msg, sizeof(NormalMessage));

		message = *info_msg;
		message.source_distance += 1;

		success = process_message(&message, info, &next);

		if (success)
		{
			error_t result;

			simdbgverbose("stdout", "Sending message to %u\n", next);

			info->ack_requested = (next != AM_BROADCAST_ADDR && info->rtx_attempts > 0);

			message.source_distance_of_sender = source_distance;
			message.time_taken_to_send = call LocalTime.get() - info->time_added;

			result = send_Normal_message_ex(&message, next, &info->ack_requested);
			if (result != SUCCESS)
			{
				// Do not penalise failing to send the message here
				info->rtx_attempts += 1;

				// If we failed to send the message, try again in a bit
				call ConsiderTimer.startOneShot(ALPHA_RETRY);

				ERROR_OCCURRED(ERROR_FAILED_TO_SEND_NORMAL, "Failed to send Normal with %" PRIu8 ", retrying\n", result);
			}
		}
		else
		{
			if (message.stage == NORMAL_ROUTE_TO_SINK && call NodeType.get() != SinkNode)
			{
				ERROR_OCCURRED(ERROR_NO_ROUTE_TO_SINK, "Cannot find route to sink.\n");
			}

			// Remove if unable to send
			info->calculate_target_attempts -= 1;

			if (info->calculate_target_attempts == 0)
			{
				// If we have failed to find somewhere to backtrack to
				// Then allow this messages to get one hop closer to the sink
				// before continuing to try to avoid the sink.
				if (message.stage == NORMAL_ROUTE_AVOID_SINK_BACKTRACK)
				{
					info_msg->stage = NORMAL_ROUTE_AVOID_SINK_1_CLOSER;
					info->calculate_target_attempts = CALCULATE_TARGET_ATTEMPTS;

					call ConsiderTimer.startOneShot(ALPHA_RETRY);
				}
				else
				{
					ERROR_OCCURRED(ERROR_FAILED_TO_FIND_MSG_ROUTE, 
						"Removing the message " NXSEQUENCE_NUMBER_SPEC " from the pool as we have failed to work out where to send it.\n",
						message.sequence_number);

					put_back_in_pool(info);
				}
			}
			else
			{
				if (info->calculate_target_attempts == NO_NEIGHBOURS_DO_POLL_THRESHOLD)
				{
					PollMessage poll_message;
					poll_message.sink_distance_of_sender = sink_distance;
					poll_message.source_distance_of_sender = source_distance;

					LOG_STDOUT(ILPROUTING_EVENT_SEND_POLL, "Couldn't calculate target several times, sending poll to get more info\n");

					call Neighbours.poll(&poll_message);
				}

				call ConsiderTimer.startOneShot(ALPHA * (CALCULATE_TARGET_ATTEMPTS - info->calculate_target_attempts));
			}
		}
	}

	event void ConsiderTimer.fired()
	{
		post consider_message_to_send();
	}

	task void send_next_away_message()
	{
		AwayMessage message;
		message.sequence_number = sequence_number_next(&away_sequence_counter);
		message.source_id = TOS_NODE_ID;
		message.sink_distance = 0;

		//simdbgverbose("stdout", "AwaySenderTimer fired.\n");

		ASSERT_MESSAGE(message.sink_distance >= 0, "dsink=" HOP_DISTANCE_SPEC, message.sink_distance);

		if (!send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			// Failed to send away message, so schedule to retry
			call AwaySenderTimer.startOneShot(AWAY_RETRY_SEND_DELAY);
		}
		else
		{
			sequence_number_increment(&away_sequence_counter);

			sink_away_messages_to_send -= 1;

			// If there are more away messages to send, then schedule the next one
			if (sink_away_messages_to_send > 0)
			{
				call AwaySenderTimer.startOneShot(SINK_AWAY_DELAY_MS);
			}
		}
	}

	event void AwaySenderTimer.fired()
	{
		post send_next_away_message();
	}

	void update_distances_from_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(source_addr, UNKNOWN_HOP_DISTANCE, rcvd->source_distance_of_sender, (rcvd->stage == NORMAL_ROUTE_AVOID_SINK_BACKTRACK));

		// When sending messages away from the sink, we cannot be sure of getting
		// a reliable source distance gradient. So do not record it.
		if (rcvd->stage != NORMAL_ROUTE_FROM_SINK)
		{
			const hop_distance_t source_distance_of_sender = hop_distance_increment(rcvd->source_distance_of_sender);
			source_distance = hop_distance_min(source_distance, source_distance_of_sender);
		}

		sink_source_distance = hop_distance_min(sink_source_distance, rcvd->sink_source_distance);
	}

	void Normal_receive_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		const SeqNoWithFlag seq_no_lookup = {rcvd->sequence_number, rcvd->source_id, rcvd->stage};

		ASSERT_MESSAGE(rcvd->source_distance >= 0, "dsrc=" HOP_DISTANCE_SPEC, rcvd->source_distance);

		update_distances_from_Normal(rcvd, source_addr);

		if (!call LruNormalSeqNos.lookup(seq_no_lookup))
		{
			call LruNormalSeqNos.insert(seq_no_lookup);

			METRIC_RCV_NORMAL(rcvd);

			METRIC_GENERIC(METRIC_GENERIC_TIME_TAKEN_TO_SEND,
				TOS_NODE_ID_SPEC "," NXSEQUENCE_NUMBER_SPEC "," TOS_NODE_ID_SPEC ",%" PRIu32,
				rcvd->source_id, rcvd->sequence_number, source_addr, rcvd->time_taken_to_send);

			// If we are routing from the sink, only do so for a short number of hops
			if (rcvd->stage == NORMAL_ROUTE_FROM_SINK)
			{
				if (sink_distance <= NORMAL_ROUTE_FROM_SINK_DISTANCE_LIMIT)
				{
					record_received_message(msg, UINT8_MAX);
				}
			}
			else
			{
				record_received_message(msg, UINT8_MAX);
			}
		}
		else
		{
			// It is possible that we get a message that we have previously received
			// If we do nothing the route will terminate
			//
			// Note there is a chance that we receive the message, and the sender
			// fails to receive the ack. This will cause a fork in the single-path route.
			if (rcvd->stage == NORMAL_ROUTE_AVOID_SINK)
			{
				// Record and switch so this message is routed towards the sink
				record_received_message(msg, NORMAL_ROUTE_TO_SINK);
			}
			else if (rcvd->stage == NORMAL_ROUTE_TO_SINK)
			{
				// This is problematic as it indicates we have a cycle on route to the sink.
				// The more likely explanation is that the path split and an earlier path
				// was processed here.
				//
				// So we choose to do nothing.
				simdbg("stdout", "Ignoring message previously received seqno=" NXSEQUENCE_NUMBER_SPEC " proxsrc=" TOS_NODE_ID_SPEC " stage=%u POSSIBLE PROBLEM CYCLE ON WAY TO SINK, OR PATH SPLIT (NO PROBLEM)\n",
					rcvd->sequence_number, source_addr, rcvd->stage);
			}
			else if (rcvd->stage == NORMAL_ROUTE_FROM_SINK)
			{
				// Don't care
			}
			else if (rcvd->stage == NORMAL_ROUTE_AVOID_SINK_BACKTRACK)
			{
				// This is problematic as it indicates we have a cycle trying to avoid the near-sink area.
				// Probably best to just give up and route to sink.

				simdbg("stdout", "Ignoring message previously received seqno=" NXSEQUENCE_NUMBER_SPEC " proxsrc=" TOS_NODE_ID_SPEC " stage=%u PROBLEM CYCLE AVOIDING SINK\n",
					rcvd->sequence_number, source_addr, rcvd->stage);

				record_received_message(msg, NORMAL_ROUTE_TO_SINK);
			}
			else if (rcvd->stage == NORMAL_ROUTE_AVOID_SINK_1_CLOSER)
			{
				ASSERT_MESSAGE(rcvd->stage != NORMAL_ROUTE_AVOID_SINK_1_CLOSER, "Do not expect to receive a message with this stage.");
			}
			else
			{
				__builtin_unreachable();
			}
		}
	}

	void Sink_receive_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		const SeqNoWithFlag seq_no_lookup = {rcvd->sequence_number, rcvd->source_id, rcvd->stage};

		ASSERT_MESSAGE(rcvd->source_distance >= 0, "dsrc=" HOP_DISTANCE_SPEC, rcvd->source_distance);

		update_distances_from_Normal(rcvd, source_addr);
		sink_source_distance = hop_distance_min(sink_source_distance, source_distance);

		if (!call LruNormalSeqNos.lookup(seq_no_lookup))
		{
			call LruNormalSeqNos.insert(seq_no_lookup);

			METRIC_RCV_NORMAL(rcvd);

			record_received_message(msg, NORMAL_ROUTE_FROM_SINK);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SinkNode: Sink_receive_Normal(msg, rcvd, source_addr); break;
		case NormalNode: Normal_receive_Normal(msg, rcvd, source_addr); break;

		case SourceNode: break;
	RECEIVE_MESSAGE_END(Normal)


	void x_snoop_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		update_distances_from_Normal(rcvd, source_addr);

		//simdbgverbose("stdout", "Snooped a normal from %u intended for %u (rcvd-dist=%d, my-dist=%d)\n",
		//  source_addr, call AMPacket.destination(msg), rcvd->landmark_distance_of_sender, landmark_distance);

		// If we snoop a normal that we have in our queue to send, should we drop attempting to send our Normal?
		/*{
			message_queue_info_t* const info = find_message_queue_info(msg);

			if (info)
			{
				simdbg("stdout", "Snooped a normal from %u that we are trying to send. Dropping our normal!!!!!!!!!!!!!!\n", source_addr);
				put_back_in_pool(info);
			}
		}*/
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Snoop)
		case SinkNode: Sink_receive_Normal(msg, rcvd, source_addr); break;

		case SourceNode:
		case NormalNode: x_snoop_Normal(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)



	void x_receive_Away(message_t* msg, const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		ASSERT_MESSAGE(rcvd->sink_distance >= 0, "dsink=" HOP_DISTANCE_SPEC, rcvd->sink_distance);

		UPDATE_NEIGHBOURS(source_addr, rcvd->sink_distance, UNKNOWN_HOP_DISTANCE, 0);

		sink_distance = hop_distance_min(sink_distance, hop_distance_increment(rcvd->sink_distance));

		if (call NodeType.get() == SourceNode)
		{
			sink_source_distance = hop_distance_min(sink_source_distance, sink_distance);
		}

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			message = *rcvd;
			message.sink_distance += 1;

			ASSERT_MESSAGE(message.sink_distance >= 0, "dsink=" HOP_DISTANCE_SPEC, message.sink_distance);

			send_Away_message(&message, AM_BROADCAST_ADDR);

			call Neighbours.slow_beacon();
		}
	}

	RECEIVE_MESSAGE_BEGIN(Away, Receive)
		case SourceNode:
		case NormalNode: x_receive_Away(msg, rcvd, source_addr); break;

		case SinkNode: break;
	RECEIVE_MESSAGE_END(Away)

	// Neighbour management

	event void Neighbours.perform_update(ni_container_t* find, const ni_container_t* given)
	{
		ni_update(find, given);
	}

	event void Neighbours.generate_beacon(BeaconMessage* message)
	{
		message->sink_distance_of_sender = sink_distance;
		message->source_distance_of_sender = source_distance;
		message->sink_source_distance = sink_source_distance;
	}

	event void Neighbours.rcv_poll(const PollMessage* rcvd, am_addr_t source_addr)
	{
		const int16_t sink_distance_of_sender_p1 = hop_distance_increment(rcvd->sink_distance_of_sender);
		const int16_t source_distance_of_sender_p1 = hop_distance_increment(rcvd->source_distance_of_sender);

		UPDATE_NEIGHBOURS(source_addr, rcvd->sink_distance_of_sender, rcvd->source_distance_of_sender, 0);

		METRIC_RCV_POLL(rcvd);

		sink_distance = hop_distance_min(sink_distance, sink_distance_of_sender_p1);
		source_distance = hop_distance_min(source_distance, source_distance_of_sender_p1);

		if (call NodeType.get() == SourceNode)
		{
			sink_source_distance = hop_distance_min(sink_source_distance, sink_distance);
		}
		if (call NodeType.get() == SinkNode)
		{
			sink_source_distance = hop_distance_min(sink_source_distance, source_distance);
		}
	}

	event void Neighbours.rcv_beacon(const BeaconMessage* rcvd, am_addr_t source_addr)
	{
		const int16_t sink_distance_of_sender_p1 = hop_distance_increment(rcvd->sink_distance_of_sender);
		const int16_t source_distance_of_sender_p1 = hop_distance_increment(rcvd->source_distance_of_sender);

		UPDATE_NEIGHBOURS(source_addr, rcvd->sink_distance_of_sender, rcvd->source_distance_of_sender, 0);

		METRIC_RCV_BEACON(rcvd);

		sink_distance = hop_distance_min(sink_distance, sink_distance_of_sender_p1);
		source_distance = hop_distance_min(source_distance, source_distance_of_sender_p1);
		sink_source_distance = hop_distance_min(sink_source_distance, rcvd->sink_source_distance);

		if (call NodeType.get() == SourceNode)
		{
			sink_source_distance = hop_distance_min(sink_source_distance, sink_distance);
		}
		if (call NodeType.get() == SinkNode)
		{
			sink_source_distance = hop_distance_min(sink_source_distance, source_distance);
		}

#ifdef LOW_POWER_LISTENING
		// If the local wakeup is 0, then we need to set the sleep length
		// in a bit now we have found our neighbours
		if (call LowPowerListening.getLocalWakeupInterval() == 0)
		{
			call StartDutyCycleTimer.startOneShot(250);
		}
#endif
	}

	command bool SeqNoWithAddrCompare.equals(const SeqNoWithAddr* a, const SeqNoWithAddr* b)
	{
		return a->seq_no == b->seq_no && a->addr == b->addr;
	}

	command bool SeqNoWithFlagCompare.equals(const SeqNoWithFlag* a, const SeqNoWithFlag* b)
	{
		return a->seq_no == b->seq_no && a->addr == b->addr && a->flag == b->flag;
	}
}
