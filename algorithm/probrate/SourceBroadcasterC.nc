#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "NormalMessage.h"
#include "DummyNormalMessage.h"

#include <Timer.h>
#include <TinyError.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_DUMMYNORMAL(msg) METRIC_RCV(DummyNormal, source_addr, source_addr, BOTTOM, 1)

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;

	uses interface Timer<TMilli> as BroadcastTimer;

	uses interface Pool<NormalMessage> as MessagePool;
	uses interface Queue<NormalMessage*> as MessageQueue;

	uses interface Packet;
	uses interface AMPacket;

	uses interface SplitControl as RadioControl;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;

	uses interface AMSend as DummyNormalSend;
	uses interface Receive as DummyNormalReceive;

	uses interface ObjectDetector;
	uses interface SourcePeriodModel;

	uses interface SequenceNumbers as NormalSeqNos;

	uses interface Random;
}

implementation
{
	double exponential_dist(double mean)
	{
		uint16_t rnd;
		double uniform_random;
		double result;

		do
		{
			rnd = call Random.rand16();
		} while (rnd == 0 || rnd == UINT16_MAX);

		// There is a reason for ignoring 0 and the maximum value.
		// When rnd is 0, then log(0) is undefined.
		// When rnd is the maximum, log(1) is 0 and the result would be 0.

		uniform_random = rnd / (double)UINT16_MAX;

		result = mean * -log(uniform_random);

		//simdbg("stdout", "rnd = %f, ln(rnd) = %f, result = %f\n", uniform_random, -log(uniform_random), result);

		return result;
	}

	typedef enum
	{
		SourceNode, SinkNode, NormalNode
	} NodeType;

	NodeType type = NormalNode;

	const char* type_to_string()
	{
		switch (type)
		{
		case SourceNode: 			return "SourceNode";
		case SinkNode:				return "SinkNode  ";
		case NormalNode:			return "NormalNode";
		default:					return "<unknown> ";
		}
	}

	uint32_t get_broadcast_period()
	{
		uint32_t broadcast_period = (uint32_t)ceil(exponential_dist(BROADCAST_PERIOD_MS));

		static int32_t average_broadcast_period = 0;
		static int32_t counts = 0;

		++counts;
		if (counts == 1)
		{
			average_broadcast_period = broadcast_period;
		}
		else
		{
			average_broadcast_period += ((int32_t)broadcast_period - average_broadcast_period) / counts;
		}

		simdbgverbose("stdout", "Broadcast period = %d then %u ave = %d count = %u\n", BROADCAST_PERIOD_MS, broadcast_period, average_broadcast_period, counts);

		return broadcast_period;

	}

	unsigned int extra_to_send = 0;

	bool busy = FALSE;
	message_t packet;

	event void Boot.booted()
	{
		simdbgverbose("Boot", "Application booted.\n");

		if (TOS_NODE_ID == SINK_NODE_ID)
		{
			type = SinkNode;
			simdbg("Node-Change-Notification", "The node has become a Sink\n");
		}

		call RadioControl.start();
	}

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			simdbgverbose("SourceBroadcasterC", "RadioControl started.\n");

			call ObjectDetector.start();
			call BroadcastTimer.startOneShot(get_broadcast_period());
		}
		else
		{
			simdbgerror("SourceBroadcasterC", "RadioControl failed to start, retrying.\n");

			call RadioControl.start();
		}
	}

	event void RadioControl.stopDone(error_t err)
	{
		simdbgverbose("SourceBroadcasterC", "RadioControl stopped.\n");
	}

	event void ObjectDetector.detect()
	{
		// The sink node cannot become a source node
		if (type != SinkNode)
		{
			METRIC_SOURCE_CHANGE("set");
			simdbg("Node-Change-Notification", "The node has become a Source\n");

			type = SourceNode;

			call SourcePeriodModel.startPeriodic();
		}
	}

	event void ObjectDetector.stoppedDetecting()
	{
		if (type == SourceNode)
		{
			call SourcePeriodModel.stop();

			type = NormalNode;

			METRIC_SOURCE_CHANGE("unset");
			simdbg("Node-Change-Notification", "The node has become a Normal\n");
		}
	}

	USE_MESSAGE(Normal);
	USE_MESSAGE(DummyNormal);

	event void SourcePeriodModel.fired()
	{
		NormalMessage* message;

		simdbgverbose("SourceBroadcasterC", "SourcePeriodModel fired.\n");

		message = call MessagePool.get();
		if (message != NULL)
		{
			message->sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
			message->source_distance = 0;
			message->source_id = TOS_NODE_ID;

			if (call MessageQueue.enqueue(message) != SUCCESS)
			{
				simdbgerror("stdout", "Failed to enqueue, should not happen!\n");
			}
			else
			{
				call NormalSeqNos.increment(TOS_NODE_ID);
			}
		}
		else
		{
			simdbgerror("stdout", "No pool space available for another Normal message.\n");
		}
	}

	event void BroadcastTimer.fired()
	{
		NormalMessage* message;

		call BroadcastTimer.startOneShot(get_broadcast_period());

		simdbgverbose("SourceBroadcasterC", "BroadcastTimer fired.\n");

		message = call MessageQueue.dequeue();

		if (message != NULL)
		{
			if (send_Normal_message(message, AM_BROADCAST_ADDR))
			{
				call MessagePool.put(message);
			}
			else
			{
				simdbgerror("stdout", "send failed, not returning memory to pool so it will be tried again\n");
			}
		}
		else
		{
			DummyNormalMessage dummy_message;

			send_DummyNormal_message(&dummy_message, AM_BROADCAST_ADDR);
		}
	}

	void Normal_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (call NormalSeqNos.before(TOS_NODE_ID, rcvd->sequence_number))
		{
			NormalMessage* forwarding_message;

			call NormalSeqNos.update(TOS_NODE_ID, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			forwarding_message = call MessagePool.get();
			if (forwarding_message != NULL)
			{
				*forwarding_message = *rcvd;
				forwarding_message->source_distance += 1;

				if (call MessageQueue.enqueue(forwarding_message) != SUCCESS)
				{
					simdbgerror("stdout", "Failed to enqueue, should not happen!\n");
				}
			}
			else
			{
				simdbgerror("stdout", "No pool space available for another Normal message.\n");
			}
		}
	}

	void Sink_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (call NormalSeqNos.before(TOS_NODE_ID, rcvd->sequence_number))
		{
			call NormalSeqNos.update(TOS_NODE_ID, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SinkNode: Sink_receive_Normal(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Normal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)


	void x_receive_DummyNormal(const DummyNormalMessage* const rcvd, am_addr_t source_addr)
	{
		METRIC_RCV_DUMMYNORMAL(rcvd);
	}

	RECEIVE_MESSAGE_BEGIN(DummyNormal, Receive)
		case SourceNode:
		case SinkNode:
		case NormalNode: x_receive_DummyNormal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(DummyNormal)
}
