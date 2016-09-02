
#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "NormalMessage.h"
#include "FakeMessage.h"

#include <CtpDebugMsg.h>
#include <Timer.h>
#include <TinyError.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance)
#define METRIC_RCV_FAKE(msg) METRIC_RCV(Fake, source_addr, msg->source_id, msg->sequence_number, msg->source_distance)

module SourceBroadcasterC
{
	provides interface CollectionDebug;

	uses interface Boot;
	uses interface Leds;

	uses interface Timer<TMilli> as BroadcastFakeTimer;

	uses interface AMPacket;

	uses interface SplitControl as RadioControl;
	uses interface RootControl;
	uses interface StdControl as RoutingControl;

	uses interface Send as NormalSend;
	uses interface Receive as NormalReceive;
	uses interface Receive as NormalSnoop;
	uses interface Intercept as NormalIntercept;

	uses interface AMSend as FakeSend;
	uses interface Receive as FakeReceive;

	uses interface MetricLogging;

	uses interface NodeType;
	uses interface MessageType;
	uses interface ObjectDetector;
	uses interface SourcePeriodModel;

	uses interface SequenceNumbers as NormalSeqNos;

	//uses interface CollectionPacket;
	//uses interface CtpInfo;
	//uses interface CtpCongestion;
}

implementation
{
	enum
	{
		SourceNode, SinkNode, NormalNode
	};

	SequenceNumber fake_sequence_counter;

	unsigned int extra_to_send = 0;

	bool busy = FALSE;
	message_t packet;

	event void Boot.booted()
	{
		simdbgverbose("Boot", "Application booted.\n");

		sequence_number_init(&fake_sequence_counter);

		call MessageType.register_pair(NORMAL_CHANNEL, "Normal");
        call MessageType.register_pair(FAKE_CHANNEL, "Fake");

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
			simdbgverbose("SourceBroadcasterC", "RadioControl started.\n");

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

	USE_MESSAGE_NO_TARGET(Normal);
	USE_MESSAGE(Fake);

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

	event void BroadcastFakeTimer.fired()
	{
		FakeMessage message;

		message.sequence_number = sequence_number_next(&fake_sequence_counter);
		message.source_distance = 0;
		message.source_id = TOS_NODE_ID;

		if (send_Fake_message(&message, AM_BROADCAST_ADDR))
		{
			sequence_number_increment(&fake_sequence_counter);
		}
	}




	void Sink_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			simdbgverbose("stdout", "%s: Sink Received unseen Normal seqno=%u srcid=%u from %u.\n",
				sim_time_string(), rcvd->sequence_number, rcvd->source_id, source_addr);

			call BroadcastFakeTimer.startOneShot(100);
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




	void x_receive_Fake(const FakeMessage* rcvd, am_addr_t source_addr)
	{
		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			message.source_distance += 1;

			send_Fake_message(&message, AM_BROADCAST_ADDR);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Fake, Receive)
		case SourceNode: break;
		case SinkNode:
		case NormalNode: x_receive_Fake(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Fake)


	// The following is simply for metric gathering.
	// The CTP debug events are hooked into so we have correctly record when a message has been sent.

	command error_t CollectionDebug.logEvent(uint8_t event_type) {
		//simdbg("stdout", "logEvent %u\n", event_type);
		return SUCCESS;
	}
	command error_t CollectionDebug.logEventSimple(uint8_t event_type, uint16_t arg) {
		//simdbg("stdout", "logEventSimple %u %u\n", event_type, arg);
		return SUCCESS;
	}
	command error_t CollectionDebug.logEventDbg(uint8_t event_type, uint16_t arg1, uint16_t arg2, uint16_t arg3) {
		//simdbg("stdout", "logEventDbg %u %u %u %u\n", event_type, arg1, arg2, arg3);
		return SUCCESS;
	}
	command error_t CollectionDebug.logEventMsg(uint8_t event_type, uint16_t msg, am_addr_t origin, am_addr_t node) {
		//simdbg("stdout", "logEventMessage %u %u %u %u\n", event_type, msg, origin, node);

		if (event_type == NET_C_FE_SENDDONE_WAITACK || event_type == NET_C_FE_SENT_MSG || event_type == NET_C_FE_FWD_MSG)
		{
			// TODO: FIXME
			// Likely to be double counting Normal message broadcasts due to METRIC_BCAST in send_Normal_message
			METRIC_BCAST(Normal, SUCCESS, UNKNOWN_SEQNO);
		}

		return SUCCESS;
	}
	command error_t CollectionDebug.logEventRoute(uint8_t event_type, am_addr_t parent, uint8_t hopcount, uint16_t metric) {
		//simdbg("stdout", "logEventRoute %u %u %u %u\n", event_type, parent, hopcount, metric);

		if (event_type == NET_C_TREE_SENT_BEACON)
		{
			METRIC_BCAST(CTPBeacon, SUCCESS, UNKNOWN_SEQNO);
		}

		else if (event_type == NET_C_TREE_RCV_BEACON)
		{
			METRIC_RCV(CTPBeacon, parent, BOTTOM, UNKNOWN_SEQNO, BOTTOM);
		}

		return SUCCESS;
	}
}
