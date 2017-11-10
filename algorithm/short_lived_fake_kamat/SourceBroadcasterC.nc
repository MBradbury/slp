#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "FakeMessage.h"
#include "NormalMessage.h"

#include <Timer.h>
#include <TinyError.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_FAKE(msg) METRIC_RCV(Fake, source_addr, msg->source_id, msg->sequence_number, BOTTOM)

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;
	uses interface Random;

	uses interface Timer<TMilli> as BroadcastNormalTimer;
	uses interface Timer<TMilli> as BroadcastFakeTimer;

	uses interface Packet;
	uses interface AMPacket;

	uses interface SplitControl as RadioControl;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;

	uses interface AMSend as FakeSend;
	uses interface Receive as FakeReceive;

	uses interface MetricLogging;
	uses interface MetricHelpers;

	uses interface NodeType;
	uses interface MessageType;
	uses interface ObjectDetector;

	uses interface SequenceNumbers as NormalSeqNos;
}

implementation
{
	enum
	{
		SourceNode, SinkNode, NormalNode, TempFakeNode
	};

	SequenceNumber fake_sequence_counter;

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

	bool busy;
	message_t packet;

	event void Boot.booted()
	{
		busy = FALSE;
		call Packet.clear(&packet);

		sequence_number_init(&fake_sequence_counter);

		call MessageType.register_pair(NORMAL_CHANNEL, "Normal");
        call MessageType.register_pair(FAKE_CHANNEL, "Fake");

		call NodeType.register_pair(SourceNode, "SourceNode");
		call NodeType.register_pair(SinkNode, "SinkNode");
		call NodeType.register_pair(NormalNode, "NormalNode");
		call NodeType.register_pair(TempFakeNode, "TempFakeNode");

		if (call NodeType.is_node_sink())
		{
			call NodeType.init(SinkNode);
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

			call ObjectDetector.start();
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

			call BroadcastNormalTimer.startPeriodic(SOURCE_PERIOD_MS);
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

	USE_MESSAGE_NO_EXTRA_TO_SEND(Normal);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Fake);

	void become_Normal(void)
	{
		call NodeType.set(NormalNode);
	}

	void become_Fake(NodeType fake_type)
	{
		if (fake_type != TempFakeNode)
		{
			assert("The perm type is not correct");
		}

		call NodeType.set(fake_type);
	}

	event void BroadcastNormalTimer.fired()
	{
		NormalMessage message;

		simdbgverbose("SourceBroadcasterC", "BroadcastNormalTimer fired.\n");

		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;

		if (send_Normal_message(&message, AM_BROADCAST_ADDR))
		{
			call NormalSeqNos.increment(TOS_NODE_ID);
		}
	}

	event void BroadcastFakeTimer.fired()
	{
		FakeMessage message;

		become_Fake(TempFakeNode);

		message.sequence_number = sequence_number_next(&fake_sequence_counter);
		message.source_id = TOS_NODE_ID;

		if (send_Fake_message(&message, AM_BROADCAST_ADDR))
		{
			sequence_number_increment(&fake_sequence_counter);
		}
		else
		{
			simdbgerror("stdout", "Failed to send fake message. Retrying...\n");
			call BroadcastFakeTimer.startOneShot(FAKE_SEND_DELAY_MS);
		}

		if (!call BroadcastFakeTimer.isRunning())
		{
			become_Normal();
		}
	}

	void process_send_fake_message(void)
	{
		if (random_float() < FAKE_PROBABILITY)
		{
			call BroadcastFakeTimer.startOneShot(FAKE_SEND_DELAY_MS);
		}
	}

	void forward_normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;

			send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);

			process_send_fake_message();
		}
	}


	void Normal_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		forward_normal(rcvd, source_addr);
	}

	void Sink_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);
		}
	}

	void Fake_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		forward_normal(rcvd, source_addr);
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SinkNode: Sink_receive_Normal(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Normal(rcvd, source_addr); break;
		case TempFakeNode: Fake_receive_Normal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)

	void forward_fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}


	void Sink_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		forward_fake(rcvd, source_addr);
	}

	void Source_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);
		}
	}

	void Normal_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		forward_fake(rcvd, source_addr);
	}

	void Fake_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		forward_fake(rcvd, source_addr);
	}

	RECEIVE_MESSAGE_BEGIN(Fake, Receive)
		case SinkNode: Sink_receive_Fake(rcvd, source_addr); break;
		case SourceNode: Source_receive_Fake(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Fake(rcvd, source_addr); break;
		case TempFakeNode: Fake_receive_Fake(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Fake)

}
