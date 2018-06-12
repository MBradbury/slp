#include "Constants.h"
#include "Common.h"

#include "SendReceiveFunctions.h"

#include "HopDistance.h"

#include "NormalMessage.h"
#include "AwayMessage.h"
#include "BeaconMessage.h"

#include <Timer.h>
#include <TinyError.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, hop_distance_increment(msg->source_distance))
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, hop_distance_increment(msg->sink_distance))
#define METRIC_RCV_BEACON(msg) METRIC_RCV(Beacon, source_addr, AM_BROADCAST_ADDR, UNKNOWN_SEQNO, UNKNOWN_HOP_DISTANCE)

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;
	uses interface Crc;

	uses interface Timer<TMilli> as AwaySenderTimer;
	uses interface Timer<TMilli> as BeaconSenderTimer;
	uses interface Timer<TMilli> as SleepIntervalTimer;

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
	uses interface MetricHelpers;

	uses interface NodeType;
	uses interface MessageType;
	uses interface SourcePeriodModel;
	uses interface ObjectDetector;

	uses interface SequenceNumbers as NormalSeqNos;
	 
	uses interface Random;
}

implementation 
{
#ifdef SLP_DEBUG
	#include "HopDistanceDebug.h"
#endif

	hop_distance_t sink_distance;
	hop_distance_t source_distance;
	hop_distance_t sink_source_distance;

	uint8_t away_messages_to_send;

	SequenceNumber away_sequence_counter;

	int16_t sleep_cycle_count;

#if defined(SINK_SRC_SINK) || (SRC_SINK_SRC)
	bool inverse_order;
#endif

	bool busy;
	message_t packet;

	uint16_t random_interval(uint16_t min, uint16_t max)
	{
		return min + call Random.rand16() / (UINT16_MAX / (max - min + 1) + 1);
	}

	uint32_t beacon_send_wait()
	{
		return 75U + random_interval(0, 50);
	}

	bool allowed_to_sleep()
	{
		const uint16_t rnd = (call Random.rand16() % 100);

		bool result;

#if defined(ALL_SLEEP)
		// Any node is allowed to sleep
		result = TRUE;

#elif defined(NO_FAR_SLEEP)
		// Nodes further than the sink-source distance do not sleep
		result = (source_distance + sink_distance < (sink_source_distance + 2 * QUIET_NODE_DISTANCE));

#else
#	error "Technique not specified"
#endif

		// Eliminate nodes too close to the sink or source
		if (source_distance != UNKNOWN_HOP_DISTANCE)
			result &= source_distance > NON_SLEEP_SOURCE;

		if (sink_distance != UNKNOWN_HOP_DISTANCE)
			result &= sink_distance > NON_SLEEP_SINK;

		// Apply the sleep probability
		result &= rnd <= SLEEP_PROBABILITY;
		
		return result;
	}

	bool is_sleep_cycle()
	{
		uint16_t i;
		for (i = 0; i < SLEEP_DEPTH; ++i)
		{
#if defined(SINK_SRC)
			if ((sink_distance - NON_SLEEP_SINK) == sleep_cycle_count + i)
			{
				return TRUE;
			}

#elif defined(SRC_SINK)
			if ((source_distance - NON_SLEEP_SOURCE) == sleep_cycle_count + i)
			{
				return TRUE;
			}

#elif defined(SINK_SRC_SINK)
			if (!inverse_order
				? (sink_distance - NON_SLEEP_SINK) == sleep_cycle_count + i
				: (source_distance - NON_SLEEP_SOURCE) == sleep_cycle_count + i)
			{
				return TRUE;
			}

#elif defined(SRC_SINK_SRC)
			if (!inverse_order
				? (source_distance - NON_SLEEP_SOURCE) == sleep_cycle_count + i
				: (sink_distance - NON_SLEEP_SINK) == sleep_cycle_count + i)
			{
				return TRUE;
			}

#else
#	error "Technique not specified"
#endif
		}

		return FALSE;
	}

	USE_MESSAGE_NO_EXTRA_TO_SEND(Normal);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Away);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Beacon);

	event void Boot.booted()
	{
		simdbgverbose("Boot", "Application booted.\n");

		sink_distance = UNKNOWN_HOP_DISTANCE;
		source_distance = UNKNOWN_HOP_DISTANCE;
		sink_source_distance = UNKNOWN_HOP_DISTANCE;

		busy = FALSE;

		sleep_cycle_count = 1;

#if defined(SINK_SRC_SINK) || (SRC_SINK_SRC)
		inverse_order = FALSE;
#endif

		sequence_number_init(&away_sequence_counter);

		away_messages_to_send = SINK_AWAY_MESSAGES_TO_SEND;

		call MessageType.register_pair(NORMAL_CHANNEL, "Normal");
		call MessageType.register_pair(AWAY_CHANNEL, "Away");
		call MessageType.register_pair(BEACON_CHANNEL, "Beacon");

		call NodeType.register_pair(SourceNode, "SourceNode");
		call NodeType.register_pair(SinkNode, "SinkNode");
		call NodeType.register_pair(NormalNode, "NormalNode");
		call NodeType.register_pair(RealSleepNode, "RealSleepNode");
		call NodeType.register_pair(NonSleepNode, "NonSleepNode");

		if (call NodeType.is_node_sink())
		{
			call NodeType.init(SinkNode);

			call AwaySenderTimer.startOneShot(1 * 1000);
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

	event void SourcePeriodModel.fired()
	{
		NormalMessage message;
		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;
		message.sink_source_distance = sink_distance;

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
		}
		else
		{
			if (away_messages_to_send > 0)
			{
				call AwaySenderTimer.startOneShot(AWAY_DELAY_MS);
			}
		}
	}

	event void BeaconSenderTimer.fired()
	{
		BeaconMessage message;
		message.sink_distance_of_sender = sink_distance;

		call Packet.clear(&packet);

		send_Beacon_message(&message, AM_BROADCAST_ADDR);
	}

	event void SleepIntervalTimer.fired()
	{
		if (is_sleep_cycle())
		{
			if (allowed_to_sleep())
			{
				call NodeType.set(RealSleepNode);
			}
			else
			{
				call NodeType.set(NonSleepNode);
			}
		}
		else
		{
			call NodeType.set(NormalNode);
		}

		sleep_cycle_count = (sleep_cycle_count + 1) % (sink_source_distance - NON_SLEEP_SOURCE - NON_SLEEP_SINK);

#if defined(SINK_SRC_SINK) || (SRC_SINK_SRC)
		// Flip inverse order when we recycle
		if (sleep_cycle_count == 0)
		{
			inverse_order = !inverse_order;
		}
#endif
	}

	void Normal_receive_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (call NormalSeqNos.before_and_update(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			METRIC_RCV_NORMAL(rcvd);

			source_distance = hop_distance_min(source_distance, hop_distance_increment(rcvd->source_distance));
			sink_source_distance = hop_distance_min(sink_source_distance, rcvd->sink_source_distance);

			forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;

			if (!call SleepIntervalTimer.isRunning())
			{
				// Start the timer
				call SleepIntervalTimer.startPeriodic(SLEEP_DURATION_MS);

				// Also signal it immediately
				signal SleepIntervalTimer.fired();
			}

			if (call NodeType.get() != RealSleepNode)
			{
				send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
			}
		}
	}

	void Sink_receive_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (call NormalSeqNos.before_and_update(rcvd->source_id, rcvd->sequence_number))
		{
			METRIC_RCV_NORMAL(rcvd);
		}
	}

	void Source_receive_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SourceNode: Normal_receive_Normal(msg, rcvd, source_addr); break;
		case SinkNode: Sink_receive_Normal(msg, rcvd, source_addr); break;

		// NonSleepNodes behave like NormalNodes
		case NonSleepNode:
		case NormalNode: Normal_receive_Normal(msg, rcvd, source_addr); break;

		// Intentionally don't do anything
		case RealSleepNode: break;
	RECEIVE_MESSAGE_END(Normal)

	void x_receive_Away(message_t* msg, const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		sink_distance = hop_distance_min(sink_distance, hop_distance_increment(rcvd->sink_distance));

		if (sequence_number_before_and_update(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;
			
			METRIC_RCV_AWAY(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.sink_distance += 1;

			call Packet.clear(&packet);
			
			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);

			call BeaconSenderTimer.startOneShot(beacon_send_wait());
		}
	}

	RECEIVE_MESSAGE_BEGIN(Away, Receive)
		case RealSleepNode:
		case NonSleepNode:
		case NormalNode:
		case SourceNode:
		case SinkNode: x_receive_Away(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Away)

	void x_receieve_Beacon(message_t* msg, const BeaconMessage* const rcvd, am_addr_t source_addr)
	{
		sink_distance = hop_distance_min(sink_distance, hop_distance_increment(rcvd->sink_distance_of_sender));

		METRIC_RCV_BEACON(rcvd);
	}

	RECEIVE_MESSAGE_BEGIN(Beacon, Receive)
		case RealSleepNode:
		case NonSleepNode:
		case NormalNode:
		case SourceNode:
		case SinkNode: x_receieve_Beacon(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Beacon)
}
