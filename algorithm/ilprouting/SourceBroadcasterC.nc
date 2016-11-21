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
} ni_container_t;

void ni_update(ni_container_t* find, ni_container_t const* given)
{
	find->sink_distance = minbot(find->sink_distance, given->sink_distance);
}

void ni_print(const char* name, size_t i, am_addr_t address, ni_container_t const* contents)
{
	simdbg_clear(name, "[%u] => addr=%u / sink-dist=%d",
		i, address, contents->sink_distance);
}

DEFINE_NEIGHBOUR_DETAIL(ni_container_t, ni, ni_update, ni_print, SLP_MAX_1_HOP_NEIGHBOURHOOD);

#define UPDATE_NEIGHBOURS(source_addr, sink_distance) \
{ \
	const ni_container_t dist = { sink_distance }; \
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

	uses interface Queue<message_queue_info_t*> as MessageQueue;
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
		}
	}

	event void ObjectDetector.stoppedDetecting()
	{
		if (call NodeType.get() == SourceNode)
		{
			call SourcePeriodModel.stop();

			call NodeType.set(NormalNode);
		}
	}

	USE_MESSAGE(Normal);
	USE_MESSAGE(Away);
	USE_MESSAGE(Beacon);

	event void SourcePeriodModel.fired()
	{
		NormalMessage message;

		simdbgverbose("SourceBroadcasterC", "SourcePeriodModel fired.\n");

		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_distance = 0;
		message.source_id = TOS_NODE_ID;

		if (send_Normal_message(&message, AM_BROADCAST_ADDR))
		{
			call NormalSeqNos.increment(TOS_NODE_ID);
		}
	}

	event void ConsiderTimer.fired()
	{
		// Consider to whom the message should be sent to

		if (!call MessageQueue.empty())
		{
			message_queue_info_t* info = call MessageQueue.head();

			NormalMessage message = *(NormalMessage*)call NormalSend.getPayload(&info->msg, sizeof(NormalMessage));
			message.source_distance += 1;

			if (send_Normal_message(&message, AM_BROADCAST_ADDR))
			{
				info = call MessageQueue.dequeue();
				call MessagePool.put(info);
			}
		}
	}

	event void AwaySenderTimer.fired()
	{
		AwayMessage message;
		message.sequence_number = sequence_number_next(&away_sequence_counter);
		message.source_id = TOS_NODE_ID;
		message.sink_distance = 0;

		sequence_number_increment(&away_sequence_counter);

		//extra_to_send = 2;
		if (!send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			call AwaySenderTimer.startOneShot(65);
		}
		else
		{
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

		return SUCCESS;
	}

	void Normal_receive_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(source_addr, BOTTOM);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			record_received_message(msg);
		}
	}

	void Sink_receive_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(source_addr, BOTTOM);

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



	void x_receive_Away(message_t* msg, const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(source_addr, rcvd->sink_distance);

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
		UPDATE_NEIGHBOURS(source_addr, rcvd->sink_distance_of_sender);

		METRIC_RCV_BEACON(rcvd);
	}

	RECEIVE_MESSAGE_BEGIN(Beacon, Receive)
		case SinkNode:
		case SourceNode:
		case NormalNode: x_receive_Beacon(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Beacon)
}
