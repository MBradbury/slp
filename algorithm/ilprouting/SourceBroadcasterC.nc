#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "NeighbourDetail.h"

#include "MessageQueueInfo.h"

#include "NormalMessage.h"
#include "AwayMessage.h"
#include "BeaconMessage.h"

#include <Timer.h>
#include <TinyError.h>

// The amount of time in ms that it takes to send a message from one node to another
#define ALPHA 100

#define SINK_AWAY_MESSAGES_TO_SEND 3

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

	uses interface SequenceNumbers as NormalSeqNos;

	uses interface LocalTime<TMilli>;

	// Messages that are queued to send
	uses interface Dictionary<SequenceNumber, message_queue_info_t*> as MessageQueue;
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

	SequenceNumber away_sequence_counter;

	int16_t sink_distance = BOTTOM;
	int16_t source_distance = BOTTOM;
	int16_t sink_source_distance = BOTTOM;

	int16_t target_buffer_size = BOTTOM;
	int16_t target_latency_ms = BOTTOM;

	// Sink variables
	int sink_away_messages_to_send;

	// Rest

	event void Boot.booted()
	{
		simdbgverbose("Boot", "Application booted.\n");

		init_ni_neighbours(&neighbours);

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
				call AwaySenderTimer.startOneShot(1 * 1000);
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
		const SequenceNumber* begin = call MessageQueue.beginKeys();
		const SequenceNumber* end = call MessageQueue.endKeys();

		simdbg("stdout", "{");

		for (; begin != end; ++begin)
		{
			const SequenceNumber key = *begin;
			message_queue_info_t** value = call MessageQueue.get(key);

			if (value)
			{
				simdbg_clear("stdout", "%" PRIu32 ": %p", key, *value);
			}
			else
			{
				simdbg_clear("stdout", "%" PRIu32 ": NULL", key);
			}

			if (begin + 1 != end)
			{
				simdbg_clear("stdout", ", ");
			}
		}

		simdbg_clear("stdout", "}\n");
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

	message_queue_info_t* find_message_queue_info(message_t* msg)
	{
		const NormalMessage* normal_message = (NormalMessage*)call NormalSend.getPayload(msg, sizeof(NormalMessage));

		return call MessageQueue.get_or_default(normal_message->sequence_number, NULL);
	}

	error_t record_received_message(message_t* msg)
	{
		bool success;

		const NormalMessage* normal_message = (NormalMessage*)call NormalSend.getPayload(msg, sizeof(NormalMessage));

		message_queue_info_t* item = call MessagePool.get();
		if (!item)
		{
			ERROR_OCCURRED(ERROR_POOL_FULL, "No pool space available for another message.\n");

			return ENOMEM;
		}

		success = call MessageQueue.put(normal_message->sequence_number, item);
		if (!success)
		{
			ERROR_OCCURRED(ERROR_QUEUE_FULL, "No queue space available for another message.\n");

			call MessagePool.put(item);

			return ENOMEM;
		}

		memcpy(&item->msg, msg, sizeof(*item));
		item->time_added = call LocalTime.get();

		item->ack_requested = FALSE;
		item->rtx_attempts = 5;

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
			const NormalMessage* normal_message = (NormalMessage*)call NormalSend.getPayload(msg, sizeof(NormalMessage));

			message_queue_info_t* info = find_message_queue_info(msg);

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

					info->rtx_attempts -= 1;

					// Give up sending this message
					if (info->rtx_attempts == 0)
					{
						call MessageQueue.remove(normal_message->sequence_number);
						call MessagePool.put(info);
					}
				}
				else
				{
					// All good
					call MessageQueue.remove(normal_message->sequence_number);
					call MessagePool.put(info);

					if (ack_requested & was_acked)
					{
						UPDATE_NEIGHBOURS_SUCCEEDED_UNICAST(target);
					}
				}

				//print_ni_neighbours("stdout", &neighbours);
			}
			else
			{
				ERROR_OCCURRED(ERROR_DICTIONARY_KEY_NOT_FOUND, "Unable to find the dict key (%" PRIu32 ") for the message\n",
					normal_message->sequence_number);

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

		message = (NormalMessage*)call NormalSend.getPayload(&msg, sizeof(NormalMessage));

		message->sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message->source_distance = 0;
		message->sink_source_distance = sink_source_distance;
		message->source_id = TOS_NODE_ID;
		message->stage = NORMAL_ROUTE_AVOID_SINK;

		// Put the message in the buffer, do not send directly.
		if (record_received_message(&msg) == SUCCESS)
		{
			call NormalSeqNos.increment(TOS_NODE_ID);
		}
	}

	am_addr_t find_next_in_avoid_sink_route(void)
	{
		// Want to find a neighbour who has a greater source distance
		// and the same or further sink distance

		// Return AM_BROADCAST_ADDR when no available nodes.

		am_addr_t chosen_address = AM_BROADCAST_ADDR;
		uint16_t i;

		ni_neighbours_t local_neighbours;
		init_ni_neighbours(&local_neighbours);

		for (i = 0; i != neighbours.size; ++i)
		{
			ni_neighbour_detail_t const* const neighbour = &neighbours.data[i];

			const int16_t neighbour_source_distance = neighbour->contents.source_distance == BOTTOM ? source_distance+1 : neighbour->contents.source_distance;

			if (
					neighbour_source_distance > source_distance &&
					(
						(sink_distance != BOTTOM && sink_source_distance != BOTTOM && sink_distance > sink_source_distance / 2) ||
						(neighbour->contents.sink_distance != BOTTOM && sink_distance != BOTTOM && neighbour->contents.sink_distance >= sink_distance)
					)
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

			chosen_address = neighbour->address;

#ifdef SLP_VERBOSE_DEBUG
			print_ni_neighbours("stdout", &local_neighbours);
#endif

			/*simdbg("stdout", "Chosen %u at index %u (rnd=%u) out of %u neighbours (their-dsink=%d my-dsink=%d) (their-dsrc=%d my-dsrc=%d)\n",
				chosen_address, neighbour_index, rnd, local_neighbours.size,
				neighbour->contents.sink_distance, sink_distance,
				neighbour->contents.source_distance, source_distance);*/
		}

		return chosen_address;
	}

	am_addr_t find_next_in_to_sink_route(void)
	{
		// Want to find a neighbour who has a smaller sink distance

		am_addr_t chosen_address;
		uint16_t i;

		ni_neighbours_t local_neighbours;
		init_ni_neighbours(&local_neighbours);

		for (i = 0; i != neighbours.size; ++i)
		{
			ni_neighbour_detail_t const* const neighbour = &neighbours.data[i];

			// TODO: need to consider BOTTOM
			if (
					neighbour->contents.sink_distance < sink_distance
			   )
			{
				insert_ni_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
			}
		}

		if (local_neighbours.size == 0)
		{
			/*simdbg("stdout", "No local neighbours to choose so broadcasting. (my-neighbours-size=%u)\n",
				neighbours.size);*/

			chosen_address = AM_BROADCAST_ADDR;
		}
		else
		{
			// Choose a neighbour with equal probabilities.
			const uint16_t rnd = call Random.rand16();
			const uint16_t neighbour_index = rnd % local_neighbours.size;
			const ni_neighbour_detail_t* const neighbour = &local_neighbours.data[neighbour_index];

			chosen_address = neighbour->address;

#ifdef SLP_VERBOSE_DEBUG
			print_ni_neighbours("stdout", &local_neighbours);
#endif

			/*simdbg("stdout", "Chosen %u at index %u (rnd=%u) out of %u neighbours (their-dsink=%d my-dsink=%d) (their-dsrc=%d my-dsrc=%d)\n",
				chosen_address, neighbour_index, rnd, local_neighbours.size,
				neighbour->contents.sink_distance, sink_distance,
				neighbour->contents.source_distance, source_distance);*/
		}

		return chosen_address;
	}

	event void ConsiderTimer.fired()
	{
		simdbgverbose("stdout", "ConsiderTimer fired. [target_buffer_size=%d, MessageQueue.count()=%u]\n",
			target_buffer_size, call MessageQueue.count());

		// Consider to whom the message should be sent to

		if ((target_buffer_size == BOTTOM && call MessageQueue.count() > 0) ||
			(target_buffer_size != BOTTOM && call MessageQueue.count() >= target_buffer_size))
		{
			am_addr_t next = AM_BROADCAST_ADDR;

			message_queue_info_t* const info = choose_message_to_send();
			NormalMessage message;

			if (info == NULL)
			{
				ERROR_OCCURRED(ERROR_UNKNOWN, "Unable to choose a message to send.\n");
				return;
			}

			message = *(NormalMessage*)call NormalSend.getPayload(&info->msg, sizeof(NormalMessage));
			message.source_distance += 1;

			switch (message.stage)
			{
				case NORMAL_ROUTE_AVOID_SINK:
				{
					next = find_next_in_avoid_sink_route();

					// When we are done with avoiding the sink, we need to head to it
					if (next == AM_BROADCAST_ADDR && /*neighbours.size > 0 &&*/ (sink_source_distance == BOTTOM || message.source_distance > sink_source_distance))
					{
						simdbg("stdout", "Switching to NORMAL_ROUTE_TO_SINK\n");
						message.stage = NORMAL_ROUTE_TO_SINK;

						next = find_next_in_to_sink_route();
					}
				} break;

				case NORMAL_ROUTE_TO_SINK:
				{
					next = find_next_in_to_sink_route();
				} break;

				default:
				{
					simdbg("stderr", "Unknown message stage\n");
					next = AM_BROADCAST_ADDR;
				} break;
			}

			if (next != AM_BROADCAST_ADDR)
			{
				info->ack_requested = (next != AM_BROADCAST_ADDR && info->rtx_attempts > 0);

				send_Normal_message(&message, next, &info->ack_requested);
			}
		}
	}

	event void AwaySenderTimer.fired()
	{
		AwayMessage message;

		simdbgverbose("stdout", "AwaySenderTimer fired.\n");

		message.sequence_number = sequence_number_next(&away_sequence_counter);
		message.source_id = TOS_NODE_ID;
		message.sink_distance = 0;

		message.target_latency_ms = SLP_TARGET_LATENCY;
		message.target_buffer_size = (uint16_t)ceil(
			(SLP_TARGET_LATENCY - (sink_source_distance == BOTTOM ? 0 : sink_source_distance) * ALPHA) /
			(double)call SourcePeriodModel.get()
		);

		if (message.target_buffer_size > SLP_SEND_QUEUE_SIZE)
		{
			ERROR_OCCURRED(ERROR_UNKNOWN, "Invalid target buffer size %u, must be <= %u\n", message.target_buffer_size, SLP_SEND_QUEUE_SIZE);
		}

		if (!send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			call AwaySenderTimer.startOneShot(65);
		}
		else
		{
			sequence_number_increment(&away_sequence_counter);

			sink_away_messages_to_send -= 1;

			if (sink_away_messages_to_send > 0)
			{
				call AwaySenderTimer.startOneShot(1 * 1000);
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

		send_Beacon_message(&message, AM_BROADCAST_ADDR);
	}

	void Normal_receive_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(source_addr, BOTTOM, rcvd->source_distance);

		source_distance = minbot(source_distance, rcvd->source_distance + 1);
		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			record_received_message(msg);
		}
	}

	void Sink_receive_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(source_addr, BOTTOM, rcvd->source_distance);

		source_distance = minbot(source_distance, rcvd->source_distance + 1);
		sink_source_distance = minbot(sink_source_distance, source_distance);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			record_received_message(msg);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SinkNode: Sink_receive_Normal(msg, rcvd, source_addr); break;
		case NormalNode: Normal_receive_Normal(msg, rcvd, source_addr); break;

		case SourceNode: break;
	RECEIVE_MESSAGE_END(Normal)


	// If the sink snoops a normal message, we may as well just deliver it
	void Sink_snoop_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(source_addr, BOTTOM, rcvd->source_distance);

		source_distance = minbot(source_distance, rcvd->source_distance + 1);
		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

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
		case SinkNode: Sink_snoop_Normal(rcvd, source_addr); break;
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

			call BeaconSenderTimer.startOneShot(100 + (call Random.rand16() % 50));
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
