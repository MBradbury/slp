#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"
#include "HopDistance.h"

#include "AwayChooseMessage.h"
#include "FakeMessage.h"
#include "NormalMessage.h"

#include <Timer.h>
#include <TinyError.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, hop_distance_increment(msg->source_distance))
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, BOTTOM, msg->sequence_number, hop_distance_increment(msg->sink_distance))
#define METRIC_RCV_CHOOSE(msg) METRIC_RCV(Choose, source_addr, BOTTOM, msg->sequence_number, hop_distance_increment(msg->sink_distance))
#define METRIC_RCV_FAKE(msg) METRIC_RCV(Fake, source_addr, msg->source_id, msg->sequence_number, UNKNOWN_HOP_DISTANCE);

#define AWAY_DELAY_MS (SOURCE_PERIOD_MS / 4)

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;
	uses interface Random;
	uses interface Crc;	

	uses interface Timer<TMilli> as BroadcastNormalTimer;
	uses interface Timer<TMilli> as AwaySenderTimer;

	uses interface Packet;
	uses interface AMPacket;

	uses interface SplitControl as RadioControl;
	uses interface PacketTimeStamp<TMilli,uint32_t>;
	uses interface LocalTime<TMilli>;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;

	uses interface AMSend as AwaySend;
	uses interface Receive as AwayReceive;

	uses interface AMSend as ChooseSend;
	uses interface Receive as ChooseReceive;

	uses interface AMSend as FakeSend;
	uses interface Receive as FakeReceive;

	uses interface MetricLogging;
	uses interface MetricHelpers;

	uses interface NodeType;
	uses interface MessageType;
	uses interface FakeMessageGenerator;
	uses interface ObjectDetector;
}

implementation
{
#ifdef SLP_DEBUG
	#include "HopDistanceDebug.h"
#endif

	SequenceNumber normal_sequence_counter;
	SequenceNumber away_sequence_counter;
	SequenceNumber choose_sequence_counter;
	SequenceNumber fake_sequence_counter;

	hop_distance_t sink_source_distance;
	hop_distance_t source_distance;
	hop_distance_t sink_distance;

	bool sink_sent_away;
	bool seen_pfs;
	bool is_pfs_candidate;

	hop_distance_t first_source_distance;

	unsigned int extra_to_send;

	typedef enum
	{
		UnknownAlgorithm, GenericAlgorithm, FurtherAlgorithm
	} Algorithm;

	Algorithm algorithm;

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

	bool should_process_choose(void)
	{
		switch (algorithm)
		{
		case GenericAlgorithm:
			return sink_source_distance == BOTTOM || source_distance == BOTTOM ||
				source_distance > (3 * sink_source_distance) / 4;

		case FurtherAlgorithm:
			return !seen_pfs && (sink_source_distance == BOTTOM || source_distance == BOTTOM ||
				source_distance > ((1 * sink_source_distance) / 2) - 1);

		default:
			return TRUE;
		}
	}

	bool pfs_can_become_normal(void)
	{
		switch (algorithm)
		{
		case GenericAlgorithm:	return TRUE;
		case FurtherAlgorithm:	return FALSE;
		default:				return FALSE;
		}
	}

	bool busy;
	message_t packet;

	event void Boot.booted()
	{
		busy = FALSE;
		call Packet.clear(&packet);

		sink_source_distance = UNKNOWN_HOP_DISTANCE;
		source_distance = UNKNOWN_HOP_DISTANCE;
		sink_distance = UNKNOWN_HOP_DISTANCE;

		sink_sent_away = FALSE;
		seen_pfs = FALSE;
		is_pfs_candidate = FALSE;

		first_source_distance = UNKNOWN_HOP_DISTANCE;

		extra_to_send = 0;

		algorithm = UnknownAlgorithm;

		sequence_number_init(&normal_sequence_counter);
		sequence_number_init(&away_sequence_counter);
		sequence_number_init(&choose_sequence_counter);
		sequence_number_init(&fake_sequence_counter);

		call MessageType.register_pair(NORMAL_CHANNEL, "Normal");
        call MessageType.register_pair(AWAY_CHANNEL, "Away");
        call MessageType.register_pair(CHOOSE_CHANNEL, "Choose");
        call MessageType.register_pair(FAKE_CHANNEL, "Fake");

		call NodeType.register_pair(SourceNode, "SourceNode");
		call NodeType.register_pair(SinkNode, "SinkNode");
		call NodeType.register_pair(NormalNode, "NormalNode");
		call NodeType.register_pair(TempFakeNode, "TempFakeNode");
		call NodeType.register_pair(PermFakeNode, "PermFakeNode");

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

	USE_MESSAGE(Normal);
	USE_MESSAGE(Away);
	USE_MESSAGE(Choose);
	USE_MESSAGE(Fake);

	event void ObjectDetector.detect()
	{
		// A sink node cannot become a source node
		if (call NodeType.get() != SinkNode)
		{
			call NodeType.set(SourceNode);

			call BroadcastNormalTimer.startPeriodic(SOURCE_PERIOD_MS);

			first_source_distance = 0;
			source_distance = 0;

			METRIC_GENERIC(METRIC_GENERIC_DUTY_CYCLE_START, "");
		}
	}

	event void ObjectDetector.stoppedDetecting()
	{
		if (call NodeType.get() == SourceNode)
		{
			call BroadcastNormalTimer.stop();

			call NodeType.set(NormalNode);

			first_source_distance = UNKNOWN_HOP_DISTANCE;
			source_distance = UNKNOWN_HOP_DISTANCE;
		}
	}

	void become_Normal(void)
	{
		call NodeType.set(NormalNode);

		call FakeMessageGenerator.stop();
	}

	void become_Fake(const AwayChooseMessage* message, uint8_t fake_type, uint32_t become_fake_time)
	{
		float rndFloat;

#ifdef SLP_VERBOSE_DEBUG
		assert(fake_type == PermFakeNode || fake_type == TempFakeNode);
#endif

		rndFloat = random_float();

		if (fake_type == PermFakeNode)
		{
			if (rndFloat <= PR_PFS)
			{
				call NodeType.set(fake_type);

				simdbgverbose("Fake-Probability-Decision",
 					"The node %u has become a PFS due to the probability %f and the randno %f\n", TOS_NODE_ID, PR_PFS, rndFloat);

				call FakeMessageGenerator.start(message, sizeof(*message), become_fake_time);
			}
			else
			{
 				simdbgverbose("Fake-Probability-Decision",
 					"The node %u has not become a PFS due to the probability %f and the randno %f\n", TOS_NODE_ID, PR_PFS, rndFloat);
			}
		}
		else if (fake_type == TempFakeNode)
		{
			if (rndFloat <= PR_TFS)
			{
				call NodeType.set(fake_type);

				simdbgverbose("Fake-Probability-Decision",
					"The node %u has become a TFS due to the probability %f and the randno %f\n", TOS_NODE_ID, PR_TFS, rndFloat);

				call FakeMessageGenerator.startLimited(message, sizeof(*message), TEMP_FAKE_DURATION_MS, become_fake_time);
			}
			else
			{
				simdbgverbose("Fake-Probability-Decision",
					"The node %u has not become a TFS due to the probability %f and the randno %f\n", TOS_NODE_ID, PR_TFS, rndFloat);
			}
		}
		else
		{
			__builtin_unreachable();
		}
	}

	void decide_not_pfs_candidate(uint16_t max_hop)
	{
		if (first_source_distance != UNKNOWN_HOP_DISTANCE && max_hop > hop_distance_increment(first_source_distance))
		{
			is_pfs_candidate = FALSE;
			call Leds.led1Off();
		}
	}

	uint16_t new_max_hop(uint16_t max_hop)
	{
		if (first_source_distance == UNKNOWN_HOP_DISTANCE)
		{
			return max_hop;
		}
		else
		{
			return max((uint16_t)first_source_distance, max_hop);
		}
	}

	event void BroadcastNormalTimer.fired()
	{
		NormalMessage message;

		simdbgverbose("SourceBroadcasterC", "BroadcastNormalTimer fired.\n");

		message.sequence_number = sequence_number_next(&normal_sequence_counter);
		message.source_distance = 0;
		message.max_hop = (sink_source_distance != UNKNOWN_HOP_DISTANCE) ? sink_source_distance : 0;
		message.source_id = TOS_NODE_ID;
		message.sink_source_distance = sink_source_distance;

		if (send_Normal_message(&message, AM_BROADCAST_ADDR))
		{
			sequence_number_increment(&normal_sequence_counter);
		}
	}

	event void AwaySenderTimer.fired()
	{
		AwayMessage message;
		message.sequence_number = sequence_number_next(&away_sequence_counter);
		message.sink_distance = 0;
		message.sink_source_distance = sink_source_distance;
		message.max_hop = new_max_hop((sink_source_distance != UNKNOWN_HOP_DISTANCE) ? sink_source_distance : 0);
		
#ifdef SPACE_BEHIND_SINK
		message.algorithm = GenericAlgorithm;
#else
		message.algorithm = FurtherAlgorithm;
#endif

		sequence_number_increment(&away_sequence_counter);

		// TODO sense repeat 3 in (Psource / 2)
		extra_to_send = 2;
		if (send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			sink_sent_away = TRUE;
		}
	}

	void Normal_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		decide_not_pfs_candidate(rcvd->max_hop);

		sink_source_distance = hop_distance_min(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			if (first_source_distance == BOTTOM)
			{
				first_source_distance = hop_distance_increment(rcvd->source_distance);
				is_pfs_candidate = TRUE;
				call Leds.led1On();
			}

			source_distance = hop_distance_min(source_distance, hop_distance_increment(rcvd->source_distance));

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.source_distance += 1;
			forwarding_message.max_hop = new_max_hop(rcvd->max_hop);

			send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Sink_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			sink_source_distance = hop_distance_min(sink_source_distance, hop_distance_increment(rcvd->source_distance));

			if (!sink_sent_away)
			{
				// Forward on the normal message to help set up
				// good distances for nodes around the source
				NormalMessage forwarding_message = *rcvd;
				forwarding_message.sink_source_distance = sink_source_distance;
				forwarding_message.source_distance += 1;
				forwarding_message.max_hop = new_max_hop(rcvd->max_hop);

				send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);

				call AwaySenderTimer.startOneShot(AWAY_DELAY_MS);
			}
		}
	}

	void Fake_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		sink_source_distance = hop_distance_min(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.source_distance += 1;
			forwarding_message.max_hop = new_max_hop(rcvd->max_hop);

			send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SourceNode: break;
		case SinkNode: Sink_receive_Normal(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Normal(rcvd, source_addr); break;
		case TempFakeNode:
		case PermFakeNode:
			Fake_receive_Normal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)


	void Source_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_source_distance = hop_distance_min(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			sink_source_distance = hop_distance_min(sink_source_distance, hop_distance_increment(rcvd->sink_distance));

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;

			extra_to_send = 1;
			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Normal_receive_Away(message_t* msg, const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		const uint32_t become_fake_time = call PacketTimeStamp.isValid(msg)
			? call PacketTimeStamp.timestamp(msg)
			: call LocalTime.get();

		decide_not_pfs_candidate(rcvd->max_hop);

		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_source_distance = hop_distance_min(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			sink_distance = hop_distance_min(sink_distance, hop_distance_increment(rcvd->sink_distance));

			if (rcvd->sink_distance == 0)
			{
				become_Fake(rcvd, TempFakeNode, become_fake_time);

				sequence_number_increment(&choose_sequence_counter);
			}

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;
			forwarding_message.max_hop = new_max_hop(rcvd->max_hop);

			extra_to_send = 1;
			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Away, Receive)
		case SinkNode: break;
		case SourceNode: Source_receive_Away(rcvd, source_addr); break;

		case NormalNode:
		case TempFakeNode:
		case PermFakeNode: Normal_receive_Away(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Away)


	void Normal_receive_Choose(message_t* msg, const ChooseMessage* const rcvd, am_addr_t source_addr)
	{
		const uint32_t become_fake_time = call PacketTimeStamp.isValid(msg)
			? call PacketTimeStamp.timestamp(msg)
			: call LocalTime.get();

		decide_not_pfs_candidate(rcvd->max_hop);

		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_source_distance = hop_distance_min(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&choose_sequence_counter, rcvd->sequence_number) && should_process_choose())
		{
			sequence_number_update(&choose_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_CHOOSE(rcvd);

			if (is_pfs_candidate)
			{
				become_Fake(rcvd, PermFakeNode, become_fake_time);
			}
			else
			{
				become_Fake(rcvd, TempFakeNode, become_fake_time);
			}
		}
	}

	RECEIVE_MESSAGE_BEGIN(Choose, Receive)
		case NormalNode: Normal_receive_Choose(msg, rcvd, source_addr); break;

		case TempFakeNode:
		case PermFakeNode:
		case SinkNode:
		case SourceNode: break;
	RECEIVE_MESSAGE_END(Choose)



	void Sink_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		sink_source_distance = hop_distance_min(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			seen_pfs |= rcvd->from_pfs;

			message.sink_source_distance = sink_source_distance;

			send_Fake_message(&message, AM_BROADCAST_ADDR);
		}
	}

	void Source_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		sink_source_distance = hop_distance_min(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			seen_pfs |= rcvd->from_pfs;
		}
	}

	void Normal_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		decide_not_pfs_candidate(rcvd->max_hop);

		sink_source_distance = hop_distance_min(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			seen_pfs |= rcvd->from_pfs;

			// TODO: Remind myself why source_distance isn't changed here!

			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.max_hop = new_max_hop(rcvd->max_hop);

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Fake_receive_Fake(message_t* msg, const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		const uint32_t receive_fake_time = call PacketTimeStamp.isValid(msg)
			? call PacketTimeStamp.timestamp(msg)
			: call LocalTime.get();

		decide_not_pfs_candidate(rcvd->max_hop);

		sink_source_distance = hop_distance_min(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			seen_pfs |= rcvd->from_pfs;

			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.max_hop = new_max_hop(rcvd->max_hop);

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);

			if (pfs_can_become_normal() &&
				call NodeType.get() == PermFakeNode &&
				rcvd->from_pfs &&
				(
					(rcvd->sender_source_distance > source_distance) ||
					(rcvd->sender_source_distance == source_distance && sink_distance < rcvd->sink_distance) ||
					(rcvd->sender_source_distance == source_distance && sink_distance == rcvd->sink_distance && TOS_NODE_ID < rcvd->source_id)
				)
				)
			{
				call FakeMessageGenerator.expireDuration(receive_fake_time);
			}
		}
	}

	RECEIVE_MESSAGE_BEGIN(Fake, Receive)
		case SinkNode: Sink_receive_Fake(rcvd, source_addr); break;
		case SourceNode: Source_receive_Fake(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Fake(rcvd, source_addr); break;
		case TempFakeNode:
		case PermFakeNode: Fake_receive_Fake(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Fake)

	event uint32_t FakeMessageGenerator.initialStartDelay()
	{
		// Note: This causes problem if the period is a factor of the duration.
		// As the node will have busy==TRUE due to sending a FakeMessage when
		// attempting to send a ChooseMessage.
		// So it has been changed to the technique used by other fake source SLP algorithms.
		return FAKE_PERIOD_MS / 4;
	}

	event uint32_t FakeMessageGenerator.calculatePeriod()
	{
		return FAKE_PERIOD_MS;
	}

	event void FakeMessageGenerator.sendFakeMessage()
	{
		FakeMessage message;

		message.sequence_number = sequence_number_next(&fake_sequence_counter);
		message.source_id = TOS_NODE_ID;

		message.sender_source_distance = source_distance;
		message.sink_distance = sink_distance;
		message.sink_source_distance = sink_source_distance;
		
		message.max_hop = new_max_hop(0);
		
		message.from_pfs = (call NodeType.get() == PermFakeNode);
		
		if (send_Fake_message(&message, AM_BROADCAST_ADDR))
		{
			sequence_number_increment(&fake_sequence_counter);
		}
	}

	event void FakeMessageGenerator.durationExpired(const void* original_message, uint8_t original_size, uint32_t duration_expired_at)
	{
		ChooseMessage message;
		memcpy(&message, original_message, sizeof(message));

		simdbgverbose("SourceBroadcasterC", "Finished sending Fake from TFS, now sending Choose.\n");

		// When finished sending fake messages from a TFS

		message.sink_source_distance = sink_source_distance;
		message.sink_distance += 1;

		extra_to_send = 2;
		send_Choose_message(&message, AM_BROADCAST_ADDR);

		become_Normal();
	}
}
