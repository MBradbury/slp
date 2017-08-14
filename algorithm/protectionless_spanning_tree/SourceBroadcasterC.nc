#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "NormalMessage.h"

#include <Timer.h>
#include <TinyError.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance)

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;

	uses interface AMPacket;

	uses interface SplitControl as RadioControl;
	uses interface StdControl as RoutingControl;
	uses interface RootControl;

	uses interface Send as NormalSend;
	uses interface Receive as NormalReceive;
	uses interface Receive as NormalSnoop;
	uses interface Intercept as NormalIntercept;

	uses interface MetricLogging;
	uses interface MetricHelpers;

	uses interface NodeType;
	uses interface MessageType;
	uses interface ObjectDetector;
	uses interface SourcePeriodModel;

	uses interface SequenceNumbers as NormalSeqNos;
}

implementation
{
	enum
	{
		SourceNode, SinkNode, NormalNode
	};

	bool busy;
	message_t packet;

	event void Boot.booted()
	{
		LOG_STDOUT_VERBOSE(EVENT_BOOTED, "booted\n");

		busy = FALSE;
		call Packet.clear(&packet);

		call MessageType.register_pair(NORMAL_CHANNEL, "Normal");

		call NodeType.register_pair(SourceNode, "SourceNode");
		call NodeType.register_pair(SinkNode, "SinkNode");
		call NodeType.register_pair(NormalNode, "NormalNode");

		if (call NodeType.is_node_sink())
		{
			call NodeType.init(SinkNode);
			call RootControl.setRoot();
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

			call RoutingControl.start();

			call ObjectDetector.start_later(5 * 1000);
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

			LOG_STDOUT(EVENT_OBJECT_DETECTED, "An object has been detected\n");

			call SourcePeriodModel.startPeriodic();
		}
	}

	event void ObjectDetector.stoppedDetecting()
	{
		if (call NodeType.get() == SourceNode)
		{
			LOG_STDOUT(EVENT_OBJECT_STOP_DETECTED, "An object has stopped being detected\n");

			call SourcePeriodModel.stop();

			call NodeType.set(NormalNode);
		}
	}

	USE_MESSAGE_NO_TARGET(Normal);

	event void SourcePeriodModel.fired()
	{
		NormalMessage message;

		simdbgverbose("SourceBroadcasterC", "SourcePeriodModel fired.\n");

		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;

		if (send_Normal_message(&message))
		{
			call NormalSeqNos.increment(TOS_NODE_ID);
		}

		simdbgverbose("stdout", "%s: Generated Normal seqno=%u at %u.\n",
			sim_time_string(), message.sequence_number, message.source_id);
	}



	void Sink_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			simdbgverbose("stdout", "%s: Sink Received unseen Normal seqno=%u srcid=%u from %u.\n",
				sim_time_string(), rcvd->sequence_number, rcvd->source_id, source_addr);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SourceNode: break;
		case SinkNode: Sink_receive_Normal(rcvd, source_addr); break;
		case NormalNode: break;
	RECEIVE_MESSAGE_END(Normal)



	void Normal_snoop_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			simdbgverbose("stdout", "%s: Normal Snooped unseen Normal data=%u seqno=%u srcid=%u from %u.\n",
				sim_time_string(), rcvd->sequence_number, rcvd->source_id, source_addr);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Snoop)
		case SourceNode: break;
		case SinkNode: break;
		case NormalNode: Normal_snoop_Normal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)



	bool Normal_intercept_Normal(NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			simdbgverbose("stdout", "%s: Normal Intercepted unseen Normal seqno=%u srcid=%u from %u.\n",
				sim_time_string(), rcvd->sequence_number, rcvd->source_id, source_addr);

			rcvd->source_distance += 1;
		}

		return TRUE;
	}

	INTERCEPT_MESSAGE_BEGIN(Normal, Intercept)
		case SourceNode: break;
		case SinkNode: break;
		case NormalNode: return Normal_intercept_Normal(rcvd, source_addr);
	INTERCEPT_MESSAGE_END(Normal)
}
