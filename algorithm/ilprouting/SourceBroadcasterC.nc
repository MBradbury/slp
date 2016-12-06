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

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, msg->sink_distance + 1)
#define METRIC_RCV_BEACON(msg) METRIC_RCV(Beacon, source_addr, BOTTOM, BOTTOM, BOTTOM)

typedef struct
{
	int16_t sink_distance;
	int16_t source_distance;
} ni_container_t;

void ni_update(ni_container_t* find, ni_container_t const* given)
{
	find->sink_distance = minbot(find->sink_distance, given->sink_distance);
	find->source_distance = minbot(find->source_distance, given->source_distance);
}

void ni_print(const char* name, size_t i, am_addr_t address, ni_container_t const* contents)
{
	simdbg_clear(name, "[%zu] => addr=%u / sink-dist=%d src-dist=%d",
		i, address, contents->sink_distance, contents->source_distance);
}

DEFINE_NEIGHBOUR_DETAIL(ni_container_t, ni, ni_update, ni_print, SLP_MAX_1_HOP_NEIGHBOURHOOD);

#define UPDATE_NEIGHBOURS(source_addr, sink_distance, source_distance) \
{ \
	const ni_container_t dist = { sink_distance, source_distance }; \
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
	uses interface Queue<message_queue_info_t*> as MessageQueue;
    uses interface Pool<message_queue_info_t> as MessagePool;

    // Cache of the recently seen sequence numbers
    uses interface Cache<SequenceNumber> as RecentlySeen;
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

	// Sink variables
	int sink_away_messages_to_send;

	// Rest

	event void Boot.booted()
	{
		simdbgverbose("Boot", "Application booted.\n");

		init_ni_neighbours(&neighbours);

		sequence_number_init(&away_sequence_counter);

		sink_away_messages_to_send = 3;

		call MessageType.register_pair(NORMAL_CHANNEL, "Normal");
		call MessageType.register_pair(AWAY_CHANNEL, "Away");

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

			call ConsiderTimer.startPeriodic(1 * 100);
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

	message_queue_info_t* find_message_queue_info(message_t* msg)
	{
		// TODO: Fix this to find the correct queue item wrt to the message
		return (call MessageQueue.empty()) ? NULL : call MessageQueue.head();
	}

	void send_Normal_done(message_t* msg, error_t error)
	{
		if (error != SUCCESS)
		{
			// Failed to send the message
		}
		else
		{
			message_queue_info_t* info = find_message_queue_info(msg);

			if (info != NULL)
			{
				if (info->ack_requested && !call NormalPacketAcknowledgements.wasAcked(msg))
				{
					// Message was sent, but no ack received
					// Leaving the message in the queue will cause it to be sent again
					// in the next consider slot.

					info->rtx_attempts -= 1;

					// Give up sending this message
					if (info->rtx_attempts == 0)
					{
						// TODO: Fix this to remove the info found earlier.
						info = call MessageQueue.dequeue();
						call MessagePool.put(info);
					}
				}
				else
				{
					// All good
					// TODO: Fix this to remove the info found earlier.
					info = call MessageQueue.dequeue();
					call MessagePool.put(info);
				}
			}
		}
	}

	event void SourcePeriodModel.fired()
	{
		NormalMessage message;

		simdbgverbose("SourceBroadcasterC", "SourcePeriodModel fired.\n");

		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_distance = 0;
		message.source_id = TOS_NODE_ID;
		message.stage = NORMAL_ROUTE_AVOID_SINK;

		if (send_Normal_message(&message, AM_BROADCAST_ADDR, NULL))
		{
			call NormalSeqNos.increment(TOS_NODE_ID);
		}
	}

	am_addr_t find_next_in_avoid_sink_route(void)
	{
		// Want to find a neighbour who has a greater source distance
		// and the same or further sink distance

		am_addr_t chosen_address;
		uint16_t i;

		ni_neighbours_t local_neighbours;
		init_ni_neighbours(&local_neighbours);

		for (i = 0; i != neighbours.size; ++i)
		{
			ni_neighbour_detail_t const* const neighbour = &neighbours.data[i];

			// TODO: need to consider BOTTOM
			if (
					neighbour->contents.source_distance > source_distance &&
					neighbour->contents.sink_distance >= sink_distance
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
		// Consider to whom the message should be sent to

		if (!call MessageQueue.empty())
		{
			am_addr_t next = AM_BROADCAST_ADDR;

			message_queue_info_t* info = call MessageQueue.head();

			NormalMessage message = *(NormalMessage*)call NormalSend.getPayload(&info->msg, sizeof(NormalMessage));
			message.source_distance += 1;

			if (message.stage == NORMAL_ROUTE_AVOID_SINK)
			{
				next = find_next_in_avoid_sink_route();

				// When we are done with avoiding the sink, we need to head to it
				if (next == AM_BROADCAST_ADDR)
				{
					message.stage = NORMAL_ROUTE_TO_SINK;
				}
			}
			else
			{
				next = find_next_in_to_sink_route();
			}

			info->ack_requested = next != AM_BROADCAST_ADDR && info->rtx_attempts > 0;

			send_Normal_message(&message, next, &info->ack_requested);
		}
	}

	event void AwaySenderTimer.fired()
	{
		AwayMessage message;
		message.sequence_number = sequence_number_next(&away_sequence_counter);
		message.source_id = TOS_NODE_ID;
		message.sink_distance = 0;

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

		send_Beacon_message(&message, AM_BROADCAST_ADDR);
	}

	error_t record_received_message(message_t* msg)
	{
		error_t status;

		message_queue_info_t* item = call MessagePool.get();
		if (!item)
		{
			ERROR_OCCURRED(ERROR_POOL_FULL, "No pool space available for another message.\n");

			return ENOMEM;
		}

		status = call MessageQueue.enqueue(item);
		if (status != SUCCESS)
		{
			ERROR_OCCURRED(ERROR_QUEUE_FULL, "No queue space available for another message.\n");

			call MessagePool.put(item);
			return status;
		}

		memcpy(&item->msg, msg, sizeof(*item));
		item->time_added = call LocalTime.get();

		item->ack_requested = FALSE;
		item->rtx_attempts = 4;

		return SUCCESS;
	}

	void Normal_receive_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(source_addr, BOTTOM, rcvd->source_distance);

		source_distance = minbot(source_distance, rcvd->source_distance + 1);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			if (record_received_message(msg) == SUCCESS)
			{
				call RecentlySeen.insert(rcvd->sequence_number);
			}
		}
	}

	void Sink_receive_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(source_addr, BOTTOM, rcvd->source_distance);

		source_distance = minbot(source_distance, rcvd->source_distance + 1);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			if (record_received_message(msg) == SUCCESS)
			{
				call RecentlySeen.insert(rcvd->sequence_number);
			}
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

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			message = *rcvd;
			message.sink_distance += 1;

			send_Away_message(&message, AM_BROADCAST_ADDR);
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
	}

	RECEIVE_MESSAGE_BEGIN(Beacon, Receive)
		case SinkNode:
		case SourceNode:
		case NormalNode: x_receive_Beacon(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Beacon)
}
