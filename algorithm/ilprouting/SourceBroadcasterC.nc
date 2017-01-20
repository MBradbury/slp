#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "NeighbourDetail.h"

#include "MessageQueueInfo.h"
#include "SeqNoWithFlag.h"

#include "NormalMessage.h"
#include "AwayMessage.h"
#include "BeaconMessage.h"

#include <Timer.h>
#include <TinyError.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, msg->sink_distance + 1)
#define METRIC_RCV_BEACON(msg) METRIC_RCV(Beacon, source_addr, BOTTOM, UNKNOWN_SEQNO, BOTTOM)

typedef struct
{
	int16_t sink_distance;
	int16_t source_distance;

	uint16_t failed_unicasts;
	uint16_t succeeded_unicasts;
} ni_container_t;

void ni_update(ni_container_t* find, ni_container_t const* given)
{
	find->sink_distance = minbot(find->sink_distance, given->sink_distance);
	find->source_distance = minbot(find->source_distance, given->source_distance);

	find->failed_unicasts += given->failed_unicasts;
	find->succeeded_unicasts += given->succeeded_unicasts;
}

void ni_print(const char* name, size_t i, am_addr_t address, ni_container_t const* contents)
{
	simdbg_clear(name, "(%zu) %u: sink-dist=%d src-dist=%d [%u/%u]",
		i, address, contents->sink_distance, contents->source_distance,
		contents->succeeded_unicasts, contents->succeeded_unicasts + contents->failed_unicasts);
}

DEFINE_NEIGHBOUR_DETAIL(ni_container_t, ni, ni_update, ni_print, SLP_MAX_1_HOP_NEIGHBOURHOOD);

#define UPDATE_NEIGHBOURS(source_addr, sink_distance, source_distance) \
{ \
	const ni_container_t dist = { sink_distance, source_distance, 0, 0 }; \
	insert_ni_neighbour(&neighbours, source_addr, &dist); \
}

#define UPDATE_NEIGHBOURS_FAILED_UNICAST(source_addr) \
{ \
	const ni_container_t dist = { BOTTOM, BOTTOM, 1, 0 }; \
	insert_ni_neighbour(&neighbours, source_addr, &dist); \
}

#define UPDATE_NEIGHBOURS_SUCCEEDED_UNICAST(source_addr) \
{ \
	const ni_container_t dist = { BOTTOM, BOTTOM, 0, 1 }; \
	insert_ni_neighbour(&neighbours, source_addr, &dist); \
}

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;
	uses interface Random;

	uses interface Timer<TMilli> as ConsiderTimer;
	uses interface Timer<TMilli> as AwaySenderTimer;
	uses interface Timer<TMilli> as BeaconSenderTimer;

	uses interface Packet;
	uses interface AMPacket;

	uses interface SplitControl as RadioControl;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;
	uses interface Receive as NormalSnoop;
	uses interface PacketAcknowledgements as NormalPacketAcknowledgements;

	uses interface AMSend as AwaySend;
	uses interface Receive as AwayReceive;

	uses interface AMSend as BeaconSend;
	uses interface Receive as BeaconReceive;

	uses interface MetricLogging;

	uses interface NodeType;
	uses interface MessageType;
	uses interface ObjectDetector;
	uses interface SourcePeriodModel;

	uses interface Cache<SeqNoWithFlag> as LruNormalSeqNos;

	uses interface LocalTime<TMilli>;

	// Messages that are queued to send
	uses interface Dictionary<SeqNoWithAddr, message_queue_info_t*> as MessageQueue;
    uses interface Pool<message_queue_info_t> as MessagePool;
}

implementation
{
	enum
	{
		SourceNode, SinkNode, NormalNode
	};

	unsigned int extra_to_send = 0;

	bool busy = FALSE;
	message_t packet;

	// All node variables
	ni_neighbours_t neighbours;

	SequenceNumber normal_sequence_counter;
	SequenceNumber away_sequence_counter;

	int16_t sink_distance = BOTTOM;
	int16_t source_distance = BOTTOM;
	int16_t sink_source_distance = BOTTOM;

	int16_t target_buffer_size = BOTTOM;
	int16_t target_latency_ms = BOTTOM;

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
		simdbgverbose("Boot", "Application booted.\n");

		init_ni_neighbours(&neighbours);

		sequence_number_init(&normal_sequence_counter);
		sequence_number_init(&away_sequence_counter);

		sink_away_messages_to_send = SINK_AWAY_MESSAGES_TO_SEND;

		call MessageType.register_pair(NORMAL_CHANNEL, "Normal");
		call MessageType.register_pair(AWAY_CHANNEL, "Away");
		call MessageType.register_pair(BEACON_CHANNEL, "Beacon");

		call NodeType.register_pair(SourceNode, "SourceNode");
		call NodeType.register_pair(SinkNode, "SinkNode");
		call NodeType.register_pair(NormalNode, "NormalNode");

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
			simdbgverbose("SourceBroadcasterC", "RadioControl started.\n");

			call ObjectDetector.start();

			if (call NodeType.get() == SinkNode)
			{
				call AwaySenderTimer.startOneShot(SINK_AWAY_DELAY_MS);
			}

			call ConsiderTimer.startPeriodic(ALPHA);
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

			call SourcePeriodModel.startPeriodic();

			source_distance = 0;
		}
	}

	event void ObjectDetector.stoppedDetecting()
	{
		if (call NodeType.get() == SourceNode)
		{
			call SourcePeriodModel.stop();

			call NodeType.set(NormalNode);

			source_distance = BOTTOM;
		}
	}

	USE_MESSAGE_ACK_REQUEST_WITH_CALLBACK(Normal);
	USE_MESSAGE(Away);
	USE_MESSAGE(Beacon);

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
				simdbg_clear("stdout", "(%" PRIu32 ",%" PRIu32 "): %p", key.seq_no, key.addr, *value);
			}
			else
			{
				simdbg_clear("stdout", "(%" PRIu32 ",%" PRIu32 "): NULL", key.seq_no, key.addr);
			}

			if (begin + 1 != end)
			{
				simdbg_clear("stdout", ", ");
			}
		}

		simdbg_clear("stdout", "}\n");
	}

	bool has_enough_messages_to_send(void)
	{
		return (target_buffer_size == BOTTOM && call MessageQueue.count() > 0) ||
		       (target_buffer_size != BOTTOM && call MessageQueue.count() > 0 && call MessageQueue.count() >= target_buffer_size);
	}

	message_queue_info_t* choose_message_to_send(void)
	{
		message_queue_info_t** const begin = call MessageQueue.begin();
		message_queue_info_t** const end = call MessageQueue.end();

		message_queue_info_t** iter = begin;

		const uint32_t current_time = call LocalTime.get();

		const int16_t distance_to_consider =
			sink_distance != BOTTOM ? sink_distance :
			(sink_source_distance != BOTTOM ? sink_source_distance : 0);

		const uint32_t min_time_to_travel = (2 + distance_to_consider) * (ALPHA + 1);

		// Cannot choose messages to send when there are no messages
		if (call MessageQueue.count() == 0)
		{
			return NULL;
		}

		//simdbg("stdout", "target buffer size %" PRIi16 " :: target latency ms %" PRIi16 "\n", target_buffer_size, target_latency_ms);

		// If we don't know our target latency, then there isn't much that can be done
		// so just send messages in FIFO order.
		if (target_latency_ms == BOTTOM)
		{
			//simdbg("stdout", "Chosen message number 0 (unknown latency)\n");

			return *begin;
		}

		// Check if there are any messages that need to be urgently sent to meet the latency deadline
		for (iter = begin; iter != end; ++iter)
		{
			message_queue_info_t* const value = *iter;

			// How long this packet has been in the queue
			const uint32_t time_since_added = current_time - value->time_added;

			if (time_since_added + min_time_to_travel >= (uint32_t)target_latency_ms)
			{
				//simdbg("stdout", "Chosen message number %ld (deadline requirement) (mtt=%" PRIu32 ")\n", iter - begin, min_time_to_travel);

				return value;
			}
		}

		// Otherwise we can just choose a random message to forward
		{
			const uint16_t rnd = call Random.rand16();
			const uint16_t idx = rnd % call MessageQueue.count();
			message_queue_info_t* const value = begin[idx];

			//simdbg("stdout", "Chosen message number %u (random)\n", idx);

			return value;
		}
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
		const NormalMessage* rcvd = (NormalMessage*)call NormalSend.getPayload(&info->msg, sizeof(NormalMessage));

		const SeqNoWithAddr seq_no_lookup = {rcvd->sequence_number, rcvd->source_id};

		call MessageQueue.remove(seq_no_lookup);
		call MessagePool.put(info);
	}

	message_queue_info_t* find_message_queue_info(message_t* msg)
	{
		const NormalMessage* rcvd = (NormalMessage*)call NormalSend.getPayload(msg, sizeof(NormalMessage));

		const SeqNoWithAddr seq_no_lookup = {rcvd->sequence_number, rcvd->source_id};

		return call MessageQueue.get_or_default(seq_no_lookup, NULL);
	}

	error_t record_received_message(message_t* msg, uint8_t switch_stage)
	{
		bool success;
		message_queue_info_t* item;

		// Check if there is already a message with this sequence number present
		// If there is then we will just overwrite it with the current message.
		item = find_message_queue_info(msg);

		if (!item)
		{
			const NormalMessage* rcvd = (NormalMessage*)call NormalSend.getPayload(msg, sizeof(NormalMessage));

			const SeqNoWithAddr seq_no_lookup = {rcvd->sequence_number, rcvd->source_id};

			item = call MessagePool.get();
			if (!item)
			{
				ERROR_OCCURRED(ERROR_POOL_FULL, "No pool space available for another message.\n");

				return ENOMEM;
			}

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

		memcpy(&item->msg, msg, sizeof(*item));

		if (switch_stage != UINT8_MAX)
		{
			NormalMessage* stored_normal_message = (NormalMessage*)call NormalSend.getPayload(&item->msg, sizeof(NormalMessage));

			stored_normal_message->stage = switch_stage;
		}

		item->time_added = call LocalTime.get();
		item->proximate_source = call AMPacket.source(msg);
		item->ack_requested = FALSE;
		item->rtx_attempts = RTX_ATTEMPTS;
		item->calculate_target_attempts = RTX_ATTEMPTS;

		return SUCCESS;
	}

	void send_Normal_done(message_t* msg, error_t error)
	{
		if (error != SUCCESS)
		{
			// Failed to send the message
			// Do nothing as this message will be considered to be resent in the future
		}
		else
		{
			message_queue_info_t* const info = find_message_queue_info(msg);

			NormalMessage* const normal_message = (NormalMessage*)call NormalSend.getPayload(&info->msg, sizeof(NormalMessage));

			if (info != NULL)
			{
				const am_addr_t target = call AMPacket.destination(msg);

				const bool ack_requested = info->ack_requested;
				const bool was_acked = call NormalPacketAcknowledgements.wasAcked(msg);

				if (ack_requested & !was_acked)
				{
					// Message was sent, but no ack received
					// Leaving the message in the queue will cause it to be sent again
					// in the next consider slot.

					UPDATE_NEIGHBOURS_FAILED_UNICAST(target);

					info->failed_neighbour_sends[failed_neighbour_sends_length(info)] = target;

					info->rtx_attempts -= 1;

					// Give up sending this message
					if (info->rtx_attempts == 0)
					{
						if (normal_message->stage == NORMAL_ROUTE_AVOID_SINK)
						{
							// If we failed to route and avoid the sink, then lets just give up and route towards the sink
							normal_message->stage = NORMAL_ROUTE_TO_SINK;
							info->rtx_attempts = RTX_ATTEMPTS;

							simdbgverbose("stdout", "Failed to route message to avoid sink, giving up and routing to sink.\n");
						}
						else
						{
							simdbgverbose("stdout", "Failed to send message at stage %u.\n", normal_message->stage);

							// Failed to route to sink, so remove from queue.
							put_back_in_pool(info);
						}
					}
				}
				else
				{
					// All good
					put_back_in_pool(info);

					if (ack_requested & was_acked)
					{
						UPDATE_NEIGHBOURS_SUCCEEDED_UNICAST(target);
					}
				}
			}
			else
			{
				ERROR_OCCURRED(ERROR_DICTIONARY_KEY_NOT_FOUND, "Unable to find the dict key (%" PRIu32 ", %" PRIu16 ") for the message\n",
					normal_message->sequence_number, normal_message->source_id);

				print_dictionary_queue();
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
	}

	bool find_next_in_avoid_sink_route(const message_queue_info_t* info, am_addr_t* next)
	{
		bool success = FALSE;
		uint16_t i;

		ni_neighbours_t local_neighbours;
		init_ni_neighbours(&local_neighbours);

		// Prefer to pick neighbours with a greater source and also greater sink distance
		for (i = 0; i != neighbours.size; ++i)
		{
			ni_neighbour_detail_t const* const neighbour = &neighbours.data[i];

			const int16_t neighbour_source_distance = neighbour->contents.source_distance == BOTTOM
				? source_distance+1
				: neighbour->contents.source_distance;

			if (
				neighbour_source_distance > source_distance &&
			
				(neighbour->contents.sink_distance != BOTTOM && sink_distance != BOTTOM &&
					neighbour->contents.sink_distance >= sink_distance) &&

				neighbour->address != info->proximate_source
			   )
			{
				insert_ni_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
			}
		}

		// Otherwise look for neighbours with a greater source distance
		// that are in the ssd/2 area
		if (local_neighbours.size == 0)
		{
			for (i = 0; i != neighbours.size; ++i)
			{
				ni_neighbour_detail_t const* const neighbour = &neighbours.data[i];

				const int16_t neighbour_source_distance = neighbour->contents.source_distance == BOTTOM
					? source_distance+1
					: neighbour->contents.source_distance;

				if (
					neighbour_source_distance > source_distance &&

					(sink_distance != BOTTOM && sink_source_distance != BOTTOM && sink_distance * 2 > sink_source_distance) &&

					neighbour->address != info->proximate_source
				   )
				{
					insert_ni_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
				}
			}
		}

		// If this is the source and the sink distance and ssd are unknown, just allow everyone.
		if (local_neighbours.size == 0 && call NodeType.get() == SourceNode &&
			(sink_distance == BOTTOM || sink_source_distance == BOTTOM))
		{
			for (i = 0; i != neighbours.size; ++i)
			{
				ni_neighbour_detail_t const* const neighbour = &neighbours.data[i];

				insert_ni_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
			}
		}

		// TODO:
		// At this point we have all the valid neighbours we could potentially choose from.
		// We now need to make sure the best neighbour is chosen.

		if (local_neighbours.size == 0)
		{
			/*simdbg("stdout", "No local neighbours to choose so broadcasting. (my-neighbours-size=%u) (my-sink-distance=%d, my-source-distance=%d)\n",
				neighbours.size, sink_distance, source_distance);

			print_ni_neighbours("stdout", &neighbours);*/
		}
		else
		{
			// Choose a neighbour with equal probabilities.
			const uint16_t rnd = call Random.rand16();
			const uint16_t neighbour_index = rnd % local_neighbours.size;
			const ni_neighbour_detail_t* const neighbour = &local_neighbours.data[neighbour_index];

			*next = neighbour->address;
			success = TRUE;

#ifdef SLP_VERBOSE_DEBUG
			print_ni_neighbours("stdout", &local_neighbours);
#endif

			/*simdbg("stdout", "Chosen %u at index %u (rnd=%u) out of %u neighbours (their-dsink=%d my-dsink=%d) (their-dsrc=%d my-dsrc=%d)\n",
				chosen_address, neighbour_index, rnd, local_neighbours.size,
				neighbour->contents.sink_distance, sink_distance,
				neighbour->contents.source_distance, source_distance);*/
		}

		return success;
	}

	bool find_next_in_avoid_sink_backtrack_route(const message_queue_info_t* info, am_addr_t* next)
	{
		// The normal message has hit a region where there are no suitable nodes
		// available. So the message will need to go closer to the source to look
		// for a better route.

		bool success = FALSE;
		uint16_t i;

		ni_neighbours_t local_neighbours;
		init_ni_neighbours(&local_neighbours);

		for (i = 0; i != neighbours.size; ++i)
		{
			ni_neighbour_detail_t const* const neighbour = &neighbours.data[i];

			if (
				// Do not send back to the previous node unless absolutely necessary
				neighbour->address != info->proximate_source &&

				neighbour->contents.sink_distance >= sink_distance
			   )
			{
				insert_ni_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
			}
		}

		if (local_neighbours.size == 0)
		{
			/*simdbg("stdout", "No local neighbours to choose so broadcasting. (my-neighbours-size=%u) (my-sink-distance=%d, my-source-distance=%d)\n",
				neighbours.size, sink_distance, source_distance);

			print_ni_neighbours("stdout", &neighbours);*/
		}
		else
		{
			// Choose a neighbour with equal probabilities.
			const uint16_t rnd = call Random.rand16();
			const uint16_t neighbour_index = rnd % local_neighbours.size;
			const ni_neighbour_detail_t* const neighbour = &local_neighbours.data[neighbour_index];

			*next = neighbour->address;
			success = TRUE;

#ifdef SLP_VERBOSE_DEBUG
			print_ni_neighbours("stdout", &local_neighbours);
#endif

			/*simdbg("stdout", "Chosen %u at index %u (rnd=%u) out of %u neighbours (their-dsink=%d my-dsink=%d) (their-dsrc=%d my-dsrc=%d)\n",
				chosen_address, neighbour_index, rnd, local_neighbours.size,
				neighbour->contents.sink_distance, sink_distance,
				neighbour->contents.source_distance, source_distance);*/
		}

		return success;
	}

	void init_bad_neighbours(const message_queue_info_t* info, am_addr_t* bad_neighbours, uint8_t* bad_neighbours_size)
	{
		uint8_t i, j;

		am_addr_t skippable_neighbours[RTX_ATTEMPTS];
		uint8_t skippable_neighbours_count[RTX_ATTEMPTS];
		uint8_t skippable_neighbours_size = 0;

		const uint8_t bad_threshold = BAD_NEIGHBOUR_THRESHOLD;

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
				skippable_neighbours_size += 1;

				skippable_neighbours[j] = bad_neighbour;
				skippable_neighbours_count[j] = 1;
			}
			else
			{
				skippable_neighbours_count[j] += 1;
			}
		}

		// Copy neighbours that are bad to the list
		for (i = 0; i != skippable_neighbours_size; ++i)
		{
			if (skippable_neighbours_count[i] >= bad_threshold)
			{
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

	bool find_next_in_to_sink_route(const message_queue_info_t* info, am_addr_t* next)
	{
		// Want to find a neighbour who has a smaller sink distance

		bool success = FALSE;
		uint16_t i;

		am_addr_t bad_neighbours[RTX_ATTEMPTS];
		uint8_t bad_neighbours_size = 0;

		ni_neighbours_t local_neighbours;
		init_ni_neighbours(&local_neighbours);

		// Find out if there are any bad neighbours present. If there are
		// then we will try to pick a neighbour other than this one.
		init_bad_neighbours(info, bad_neighbours, &bad_neighbours_size);

		// Try sending to neighbours that are closer to the sink and further from the source
		if (local_neighbours.size == 0)
		{
			for (i = 0; i != neighbours.size; ++i)
			{
				ni_neighbour_detail_t const* const neighbour = &neighbours.data[i];

				if (
					neighbour->contents.sink_distance != BOTTOM && sink_distance != BOTTOM &&
					neighbour->contents.sink_distance < sink_distance &&

					neighbour->contents.source_distance != BOTTOM && source_distance != BOTTOM &&
					neighbour->contents.source_distance >= source_distance &&

					!neighbour_present(bad_neighbours, bad_neighbours_size, neighbour->address)
				   )
				{
					insert_ni_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
				}
			}
		}

		// Try sending to neighbours closer to the sink
		if (local_neighbours.size == 0)
		{
			for (i = 0; i != neighbours.size; ++i)
			{
				ni_neighbour_detail_t const* const neighbour = &neighbours.data[i];

				if (
					neighbour->contents.sink_distance != BOTTOM && sink_distance != BOTTOM &&
					neighbour->contents.sink_distance < sink_distance &&

					!neighbour_present(bad_neighbours, bad_neighbours_size, neighbour->address)
				   )
				{
					insert_ni_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
				}
			}
		}

		// Try sliding about same-sink distance nodes
		if (local_neighbours.size == 0)
		{
			for (i = 0; i != neighbours.size; ++i)
			{
				ni_neighbour_detail_t const* const neighbour = &neighbours.data[i];

				if (
					neighbour->contents.sink_distance != BOTTOM && sink_distance != BOTTOM &&
					neighbour->contents.sink_distance == sink_distance &&

					!neighbour_present(bad_neighbours, bad_neighbours_size, neighbour->address)
				   )
				{
					insert_ni_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
				}
			}
		}

		// Just pick a random neighbour that wasn't the one we just came from
		if (local_neighbours.size == 0)
		{
			for (i = 0; i != neighbours.size; ++i)
			{
				ni_neighbour_detail_t const* const neighbour = &neighbours.data[i];

				if (
					neighbour->address != info->proximate_source &&

					!neighbour_present(bad_neighbours, bad_neighbours_size, neighbour->address)
				   )
				{
					insert_ni_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
				}
			}
		}

		// Just pick a random neighbour that wasn't the one we just came from.
		// Also allow potentially bad neighbours.
		if (local_neighbours.size == 0)
		{
			for (i = 0; i != neighbours.size; ++i)
			{
				ni_neighbour_detail_t const* const neighbour = &neighbours.data[i];

				if (
					neighbour->address != info->proximate_source
				   )
				{
					insert_ni_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
				}
			}
		}

		if (local_neighbours.size == 0)
		{
			/*simdbg("stdout", "No local neighbours to choose so broadcasting. (my-neighbours-size=%u)\n",
				neighbours.size);*/
		}
		else
		{
			// Choose a neighbour with equal probabilities.
			const uint16_t rnd = call Random.rand16();
			const uint16_t neighbour_index = rnd % local_neighbours.size;
			const ni_neighbour_detail_t* const neighbour = &local_neighbours.data[neighbour_index];

			*next = neighbour->address;
			success = TRUE;

#ifdef SLP_VERBOSE_DEBUG
			print_ni_neighbours("stdout", &local_neighbours);
#endif

			/*simdbg("stdout", "Chosen %u at index %u (rnd=%u) out of %u neighbours (their-dsink=%d my-dsink=%d) (their-dsrc=%d my-dsrc=%d)\n",
				chosen_address, neighbour_index, rnd, local_neighbours.size,
				neighbour->contents.sink_distance, sink_distance,
				neighbour->contents.source_distance, source_distance);*/
		}

		return success;
	}

	bool find_next_in_from_sink_route(const message_queue_info_t* info, am_addr_t* next)
	{
		bool success = FALSE;
		uint16_t i;

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
		if (local_neighbours.size == 0)
		{
			for (i = 0; i != neighbours.size; ++i)
			{
				ni_neighbour_detail_t const* const neighbour = &neighbours.data[i];

				if (
					// Do not send back to the previous node
					neighbour->address != info->proximate_source &&

					neighbour->contents.sink_distance > sink_distance
				   )
				{
					insert_ni_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
				}
			}
		}

		// Accept nodes that are the same sink distance away
		if (local_neighbours.size == 0)
		{
			for (i = 0; i != neighbours.size; ++i)
			{
				ni_neighbour_detail_t const* const neighbour = &neighbours.data[i];

				if (
					// Do not send back to the previous node
					neighbour->address != info->proximate_source &&

					neighbour->contents.sink_distance == sink_distance
				   )
				{
					insert_ni_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
				}
			}
		}

		if (local_neighbours.size == 0)
		{
			/*simdbg("stdout", "No local neighbours to choose so broadcasting. (my-neighbours-size=%u)\n",
				neighbours.size);*/

			*next = AM_BROADCAST_ADDR;
			success = TRUE;
		}
		else
		{
			// Choose a neighbour with equal probabilities.
			const uint16_t rnd = call Random.rand16();
			const uint16_t neighbour_index = rnd % local_neighbours.size;
			const ni_neighbour_detail_t* const neighbour = &local_neighbours.data[neighbour_index];

			*next = neighbour->address;
			success = TRUE;

#ifdef SLP_VERBOSE_DEBUG
			print_ni_neighbours("stdout", &local_neighbours);
#endif

			/*simdbg("stdout", "Chosen %u at index %u (rnd=%u) out of %u neighbours (their-dsink=%d my-dsink=%d) (their-dsrc=%d my-dsrc=%d)\n",
				chosen_address, neighbour_index, rnd, local_neighbours.size,
				neighbour->contents.sink_distance, sink_distance,
				neighbour->contents.source_distance, source_distance);*/
		}

		return success;
	}


	event void ConsiderTimer.fired()
	{
		simdbgverbose("stdout", "ConsiderTimer fired. [target_buffer_size=%d, MessageQueue.count()=%u]\n",
			target_buffer_size, call MessageQueue.count());

		// Consider to whom the message should be sent to

		// If we have no neighbour knowledge, then don't start sending
		if (neighbours.size == 0)
		{
			return;
		}

		if (has_enough_messages_to_send())
		{
			am_addr_t next = AM_BROADCAST_ADDR;
			bool success = FALSE;

			message_queue_info_t* const info = choose_message_to_send();
			NormalMessage message;

			if (info == NULL)
			{
				ERROR_OCCURRED(ERROR_UNKNOWN, "Unable to choose a message to send (call MessageQueue.count()=%u,target_buffer_size=%u).\n",
					call MessageQueue.count(), target_buffer_size);
				return;
			}

			message = *(NormalMessage*)call NormalSend.getPayload(&info->msg, sizeof(NormalMessage));
			message.source_distance += 1;

			// If we have hit the maximum walk distance, switch to routing to sink
			if (message.source_distance >= SLP_MAX_WALK_LENGTH)
			{
				message.stage = NORMAL_ROUTE_TO_SINK;

				simdbgverbose("stdout", "Switching to NORMAL_ROUTE_TO_SINK as max walk length has been hit\n");
			}

			switch (message.stage)
			{
				case NORMAL_ROUTE_AVOID_SINK:
				{
					success = find_next_in_avoid_sink_route(info, &next);

					// When we are done with avoiding the sink, we need to head to it
					if (!success)
					{
						if (sink_source_distance != BOTTOM && source_distance < sink_source_distance)
						{
							// We are too close to the source and it is likely that we haven't yet gone
							// around the sink. So lets try backtracking and finding another route.

							message.stage = NORMAL_ROUTE_AVOID_SINK_BACKTRACK;

							success = find_next_in_avoid_sink_backtrack_route(info, &next);

							simdbgverbose("stdout", "Switching from NORMAL_ROUTE_AVOID_SINK to NORMAL_ROUTE_AVOID_SINK_BACKTRACK chosen %u\n", next);

							// Couldn't work out where to backtrack to, so lets just go to the sink
							if (!success)
							{
								message.stage = NORMAL_ROUTE_TO_SINK;

								success = find_next_in_to_sink_route(info, &next);

								simdbgverbose("stdout", "Switching to NORMAL_ROUTE_TO_SINK (giving up) chosen %u\n", next);
							}
						}
						else
						{
							// No neighbours left to choose from, when far from the source

							message.stage = NORMAL_ROUTE_TO_SINK;

							success = find_next_in_to_sink_route(info, &next);

							simdbgverbose("stdout", "Switching from NORMAL_ROUTE_AVOID_SINK to NORMAL_ROUTE_TO_SINK chosen %u\n", next);
						}
					}
				} break;

				case NORMAL_ROUTE_AVOID_SINK_BACKTRACK:
				{
					// Received a message after backtracking, now need to pick a better direction to send it in.
					
					message.stage = NORMAL_ROUTE_AVOID_SINK;

					success = find_next_in_avoid_sink_route(info, &next);

					simdbgverbose("stdout", "Switching from NORMAL_ROUTE_AVOID_SINK_BACKTRACK to NORMAL_ROUTE_AVOID_SINK chosen %u\n", next);

				} break;

				case NORMAL_ROUTE_TO_SINK:
				{
					success = find_next_in_to_sink_route(info, &next);
				} break;

				case NORMAL_ROUTE_FROM_SINK:
				{
					// AM_BROADCAST_ADDR is valid for this function
					success = find_next_in_from_sink_route(info, &next);
				} break;

				default:
				{
					simdbgverbose("stderr", "Unknown message stage\n");
				} break;
			}

			if (success)
			{
				info->ack_requested = (next != AM_BROADCAST_ADDR && info->rtx_attempts > 0);

				send_Normal_message(&message, next, &info->ack_requested);
			}
			else
			{
				if (message.stage == NORMAL_ROUTE_TO_SINK && call NodeType.get() != SinkNode)
				{
					ERROR_OCCURRED(ERROR_UNKNOWN, "Cannot find route to sink.\n");
				}

				// Remove if unable to send
				info->calculate_target_attempts -= 1;

				if (info->calculate_target_attempts == 0)
				{
					simdbgverbose("stdout", "Removing the message %" PRIu32 " from the pool as we have failed to work out where to send it.\n",
						message.sequence_number);

					put_back_in_pool(info);
				}
			}
		}
	}

	event void AwaySenderTimer.fired()
	{
		AwayMessage message;
		int32_t calc_target_buffer_size;

		simdbgverbose("stdout", "AwaySenderTimer fired.\n");

		message.sequence_number = sequence_number_next(&away_sequence_counter);
		message.source_id = TOS_NODE_ID;
		message.sink_distance = 0;
		message.target_latency_ms = SLP_TARGET_LATENCY_MS;

		calc_target_buffer_size = (int32_t)ceil(
			(SLP_TARGET_LATENCY_MS /*- (sink_source_distance == BOTTOM ? 0 : sink_source_distance) * ALPHA*/) /
			(double)SLP_FASTEST_SOURCE_PERIOD_MS
		);

		if (calc_target_buffer_size > SLP_SEND_QUEUE_SIZE)
		{
			ERROR_OCCURRED(ERROR_UNKNOWN, "Invalid target buffer size %u, must be <= %u\n", calc_target_buffer_size, SLP_SEND_QUEUE_SIZE);
			calc_target_buffer_size = SLP_SEND_QUEUE_SIZE - 1;
		}

		if (calc_target_buffer_size <= 0)
		{
			ERROR_OCCURRED(ERROR_UNKNOWN, "Invalid target buffer size %u, must be > 0\n", calc_target_buffer_size);
			calc_target_buffer_size = 1;
		}

		message.target_buffer_size = (uint16_t)calc_target_buffer_size;

		if (!send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			// Failed to send away message, so schedule to retry
			call AwaySenderTimer.startOneShot(AWAY_BEACON_RETRY_SEND_DELAY);
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

	event void BeaconSenderTimer.fired()
	{
		BeaconMessage message;
		message.sink_distance_of_sender = sink_distance;
		message.source_distance_of_sender = source_distance;
		message.target_buffer_size_of_sender = target_buffer_size;
		message.target_latency_ms_of_sender = target_latency_ms;

		if (!send_Beacon_message(&message, AM_BROADCAST_ADDR))
		{
			call BeaconSenderTimer.startOneShot(AWAY_BEACON_RETRY_SEND_DELAY);
		}
	}

	void Normal_receive_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		const SeqNoWithFlag seq_no_lookup = {rcvd->sequence_number, rcvd->source_id, rcvd->stage, 0};

		UPDATE_NEIGHBOURS(source_addr, BOTTOM, rcvd->source_distance);

		source_distance = minbot(source_distance, rcvd->source_distance + 1);
		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (!call LruNormalSeqNos.lookup(seq_no_lookup))
		{
			call LruNormalSeqNos.insert(seq_no_lookup);

			METRIC_RCV_NORMAL(rcvd);

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
			// It is possible that we get a message that we have previously 
			// If we do nothing the route will terminate
			//
			// Note there is a chance that we receive the message, and the sender
			// fails to receive the ack. This will cause a fork in the single-path route.
			if (rcvd->stage == NORMAL_ROUTE_AVOID_SINK)
			{
				// Record and switch so this message is routed towards the sink
				record_received_message(msg, NORMAL_ROUTE_TO_SINK);
			}
		}
	}

	void Sink_receive_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		const SeqNoWithFlag seq_no_lookup = {rcvd->sequence_number, rcvd->source_id, rcvd->stage, 0};

		UPDATE_NEIGHBOURS(source_addr, BOTTOM, rcvd->source_distance);

		source_distance = minbot(source_distance, rcvd->source_distance + 1);
		sink_source_distance = minbot(sink_source_distance, source_distance);
		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

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


	// If the sink snoops a normal message, we may as well just deliver it
	void Sink_snoop_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		const SeqNoWithFlag seq_no_lookup = {rcvd->sequence_number, rcvd->source_id, rcvd->stage, 0};

		UPDATE_NEIGHBOURS(source_addr, BOTTOM, rcvd->source_distance);

		source_distance = minbot(source_distance, rcvd->source_distance + 1);
		sink_source_distance = minbot(sink_source_distance, source_distance);
		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (!call LruNormalSeqNos.lookup(seq_no_lookup))
		{
			call LruNormalSeqNos.insert(seq_no_lookup);

			METRIC_RCV_NORMAL(rcvd);

			record_received_message(msg, NORMAL_ROUTE_FROM_SINK);
		}
	}

	void x_snoop_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(source_addr, BOTTOM, rcvd->source_distance);

		source_distance = minbot(source_distance, rcvd->source_distance + 1);
		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		//simdbgverbose("stdout", "Snooped a normal from %u intended for %u (rcvd-dist=%d, my-dist=%d)\n",
		//  source_addr, call AMPacket.destination(msg), rcvd->landmark_distance_of_sender, landmark_distance);
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Snoop)
		case SourceNode: x_snoop_Normal(rcvd, source_addr); break;
		case SinkNode: Sink_snoop_Normal(msg, rcvd, source_addr); break;
		case NormalNode: x_snoop_Normal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)



	void x_receive_Away(message_t* msg, const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(source_addr, rcvd->sink_distance, BOTTOM);

		sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);

		if (call NodeType.get() == SourceNode)
		{
			sink_source_distance = minbot(sink_source_distance, sink_distance);
		}

		target_buffer_size = rcvd->target_buffer_size;
		target_latency_ms = rcvd->target_latency_ms;

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			message = *rcvd;
			message.sink_distance += 1;

			send_Away_message(&message, AM_BROADCAST_ADDR);

			call BeaconSenderTimer.startOneShot(BEACON_SEND_DELAY_FIXED + (call Random.rand16() % BEACON_SEND_DELAY_RANDOM));
		}
	}

	RECEIVE_MESSAGE_BEGIN(Away, Receive)
		case SourceNode:
		case NormalNode: x_receive_Away(msg, rcvd, source_addr); break;

		case SinkNode: break;
	RECEIVE_MESSAGE_END(Away)


	void x_receive_Beacon(const BeaconMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(source_addr, rcvd->sink_distance_of_sender, rcvd->source_distance_of_sender);

		METRIC_RCV_BEACON(rcvd);

		sink_distance = minbot(sink_distance, botinc(rcvd->sink_distance_of_sender));
		source_distance = minbot(source_distance, botinc(rcvd->source_distance_of_sender));

		if (call NodeType.get() == SourceNode)
		{
			sink_source_distance = minbot(sink_source_distance, sink_distance);
		}
		if (call NodeType.get() == SinkNode)
		{
			sink_source_distance = minbot(sink_source_distance, source_distance);
		}

		if (rcvd->target_buffer_size_of_sender != BOTTOM)
		{
			target_buffer_size = rcvd->target_buffer_size_of_sender;
		}

		if (rcvd->target_latency_ms_of_sender != BOTTOM)
		{
			target_latency_ms = rcvd->target_latency_ms_of_sender;
		}
	}

	RECEIVE_MESSAGE_BEGIN(Beacon, Receive)
		case SinkNode:
		case SourceNode:
		case NormalNode: x_receive_Beacon(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Beacon)
}
