#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "NormalMessage.h"
#include "AwayMessage.h"
#include "DisableMessage.h"

#include <Timer.h>
#include <TinyError.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, msg->sink_distance + 1)
#define METRIC_RCV_DISABLE(msg) METRIC_RCV(Disable, source_addr, msg->source_id, UNKNOWN_SEQNO, BOTTOM)

#define AWAY_DELAY_MS 200

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;

	uses interface Packet;
	uses interface AMPacket;

	uses interface SplitControl as RadioControl;

	uses interface Timer<TMilli> as AwaySenderTimer;
	uses interface Timer<TMilli> as DisableSenderTimer;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;

	uses interface AMSend as AwaySend;
	uses interface Receive as AwayReceive;

	uses interface AMSend as DisableSend;
	uses interface Receive as DisableReceive;

	uses interface MetricLogging;

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

	SequenceNumber away_sequence_counter;
	SequenceNumber disable_sequence_counter;

	int32_t sink_distance;
	int32_t source_distance;

	int32_t disable_radius;

	int away_messages_to_send;

	bool sent_disable;

	event void Boot.booted()
	{
		simdbgverbose("Boot", "Application booted.\n");

		busy = FALSE;
		call Packet.clear(&packet);

		sequence_number_init(&away_sequence_counter);
		sequence_number_init(&disable_sequence_counter);

		sink_distance = BOTTOM;
		source_distance = BOTTOM;

		disable_radius = BOTTOM;

		away_messages_to_send = 3;

		sent_disable = FALSE;

		call MessageType.register_pair(NORMAL_CHANNEL, "Normal");
		call MessageType.register_pair(AWAY_CHANNEL, "Away");
		call MessageType.register_pair(DISABLE_CHANNEL, "Disable");

		call NodeType.register_pair(SourceNode, "SourceNode");
		call NodeType.register_pair(SinkNode, "SinkNode");
		call NodeType.register_pair(NormalNode, "NormalNode");

		if (call NodeType.is_node_sink())
		{
			call NodeType.init(SinkNode);
			sink_distance = 0;

			call AwaySenderTimer.startOneShot(5 * AWAY_DELAY_MS);
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

			call Leds.led2On();

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

		call Leds.led2Off();
	}

	event void ObjectDetector.detect()
	{
		// A sink node cannot become a source node
		if (call NodeType.get() != SinkNode)
		{
			call NodeType.set(SourceNode);

			source_distance = 0;

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

	USE_MESSAGE_NO_EXTRA_TO_SEND(Normal);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Away);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Disable);

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

	event void AwaySenderTimer.fired()
	{
		AwayMessage message;
		message.sequence_number = sequence_number_next(&away_sequence_counter);
		message.source_id = TOS_NODE_ID;
		message.sink_distance = 0;

		if (send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			sequence_number_increment(&away_sequence_counter);

			away_messages_to_send -= 1;

			if (away_messages_to_send > 0)
			{
				call AwaySenderTimer.startOneShot(AWAY_DELAY_MS);
			}
		}
		else
		{
			call AwaySenderTimer.startOneShot(AWAY_DELAY_MS);
		}
	}

	event void DisableSenderTimer.fired()
	{
		DisableMessage disable_message;
		disable_message.sequence_number = sequence_number_next(&disable_sequence_counter);
		disable_message.source_id = TOS_NODE_ID;
		disable_message.hop_limit = (int16_t)disable_radius;
		disable_message.sink_source_distance = source_distance;

		if (send_Disable_message(&disable_message, AM_BROADCAST_ADDR))
		{
			sequence_number_increment(&disable_sequence_counter);
		}
		else
		{
			call DisableSenderTimer.startOneShot(25);
		}
	}

	void Normal_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		source_distance = minbot(source_distance, rcvd->source_distance + 1);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			simdbgverbose("SourceBroadcasterC", "Received unseen Normal seqno=" NXSEQUENCE_NUMBER_SPEC " from %u.\n",
				rcvd->sequence_number, source_addr);

			forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;

			send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Sink_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		source_distance = minbot(source_distance, rcvd->source_distance + 1);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			if (!sent_disable)
			{
				const int CONE_WIDTH = 6;

				disable_radius = (int32_t)ceil((2 * source_distance + CONE_WIDTH) / (2 * M_PI));

				call DisableSenderTimer.startOneShot(25);

				sent_disable = TRUE;
			}
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SinkNode: Sink_receive_Normal(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Normal(rcvd, source_addr); break;
		case SourceNode: break;
	RECEIVE_MESSAGE_END(Normal)


	void x_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.sink_distance += 1;

			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Away, Receive)
		case SinkNode:
		case NormalNode: x_receive_Away(rcvd, source_addr); break;
		case SourceNode: break;
	RECEIVE_MESSAGE_END(Away)


	void Normal_receive_Disable(const DisableMessage* const rcvd, am_addr_t source_addr)
	{
		if (sequence_number_before(&disable_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&disable_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_DISABLE(rcvd);

			if (rcvd->hop_limit > 0)
			{
				DisableMessage forwarding_message = *rcvd;

				send_Disable_message(&forwarding_message, AM_BROADCAST_ADDR);
			}

			if (
				// Create the inner disabled ring and the outer disabled ring of nodes
				sink_distance != BOTTOM && sink_distance > PROTECTED_SINK_HOPS && sink_distance < rcvd->hop_limit &&

				// Create the exit cone
				source_distance != BOTTOM && rcvd->sink_source_distance >= source_distance - sink_distance &&

				// Protect nodes by the source
				source_distance > 1)
			{
				call RadioControl.stop();
			}
		}
	}

	RECEIVE_MESSAGE_BEGIN(Disable, Receive)
		case SinkNode: break;
		case NormalNode: Normal_receive_Disable(rcvd, source_addr); break;
		case SourceNode: break;
	RECEIVE_MESSAGE_END(Disable)
}
