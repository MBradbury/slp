#include "Constants.h"
#include "Common.h"

#define SLP_SEND_ANY_DONE_CALLBACK
#include "SendReceiveFunctions.h"

#include "HopDistance.h"

#include "AwayMessage.h"
#include "ChooseMessage.h"
#include "FakeMessage.h"
#include "NormalMessage.h"
#include "NotifyMessage.h"

#include <Timer.h>
#include <TinyError.h>
#include <scale.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, hop_distance_increment(msg->source_distance))
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, hop_distance_increment(msg->sink_distance))
#define METRIC_RCV_CHOOSE(msg) METRIC_RCV(Choose, source_addr, msg->source_id, msg->sequence_number, hop_distance_increment(msg->sink_distance))
#define METRIC_RCV_FAKE(msg) METRIC_RCV(Fake, source_addr, msg->source_id, msg->sequence_number, UNKNOWN_HOP_DISTANCE)
#define METRIC_RCV_NOTIFY(msg) METRIC_RCV(Notify, source_addr, msg->source_id, msg->sequence_number, hop_distance_increment(msg->source_distance))

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

	uses interface AMSend as NotifySend;
	uses interface Receive as NotifyReceive;

	uses interface MetricLogging;
	uses interface MetricHelpers;

	uses interface NodeType;
	uses interface MessageType;
	uses interface FakeMessageGenerator;
	uses interface ObjectDetector;

	uses interface SequenceNumbers as NormalSeqNos;
}

implementation
{
#ifdef SLP_DEBUG
	#include "HopDistanceDebug.h"
#endif

	SequenceNumber away_sequence_counter;
	SequenceNumber choose_sequence_counter;
	SequenceNumber fake_sequence_counter;
	SequenceNumber notify_sequence_counter;

	SequenceNumber source_fake_sequence_counter;
	uint32_t source_fake_sequence_increments;

	uint8_t choose_rtx_limit;

	uint16_t fake_rcv_ratio;

	hop_distance_t sink_source_distance;
	hop_distance_t source_distance;
	hop_distance_t sink_distance;

	bool sink_received_choose_reponse;
	bool seen_pfs;
	bool is_pfs_candidate;

	hop_distance_t first_source_distance;

	unsigned int away_messages_to_send;

	bool send_choose_on_next_send_done;
	bool send_fake_on_next_send_done;

	typedef enum
	{
		UnknownAlgorithm, GenericAlgorithm, FurtherAlgorithm
	} Algorithm;

	Algorithm algorithm;

	uint16_t random_interval(uint16_t min, uint16_t max)
	{
		return min + call Random.rand16() / (UINT16_MAX / (max - min + 1) + 1);
	}

	bool should_process_choose(void)
	{
		switch (algorithm)
		{
		case GenericAlgorithm:
			return sink_source_distance == UNKNOWN_HOP_DISTANCE || source_distance == UNKNOWN_HOP_DISTANCE ||
				source_distance > (4 * sink_source_distance) / 5;

		case FurtherAlgorithm:
			return !seen_pfs && (sink_source_distance == UNKNOWN_HOP_DISTANCE || source_distance == UNKNOWN_HOP_DISTANCE ||
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

#if defined(PB_SINK_APPROACH)
	hop_distance_t get_dist_to_pull_back(void)
	{
		int32_t distance = 0;

		switch (algorithm)
		{
		case GenericAlgorithm:
			// When reasoning we want to pull back in terms of the sink distance.
			// However, the Dsrc - the Dss gives a good approximation of the Dsink.
			// It has the added benefit that this is only true when the TFS is further from
			// the source than the sink is.
			// This means that TFSs near the source will send fewer messages.
			if (source_distance == UNKNOWN_HOP_DISTANCE || sink_source_distance == UNKNOWN_HOP_DISTANCE)
			{
				distance = sink_distance;
			}
			else
			{
				distance = source_distance - sink_source_distance;
			}
			break;

		default:
		case FurtherAlgorithm:
			distance = max(sink_source_distance, sink_distance);
			break;
		}

		distance = max(distance, 1);
		
		return distance;	
	}

#elif defined(PB_ATTACKER_EST_APPROACH)
	hop_distance_t get_dist_to_pull_back(void)
	{
		int32_t distance = 0;

		switch (algorithm)
		{
		case GenericAlgorithm:
			if (sink_distance != UNKNOWN_HOP_DISTANCE)
			{
				distance = sink_distance + sink_distance;
			}
			else
			{
				distance = sink_source_distance;
			}
			break;

		default:
		case FurtherAlgorithm:
			distance = max(sink_source_distance, sink_distance);
			break;
		}

		distance = max(distance, 1);
		
		return distance;
	}

#else
#	error "Technique not specified"
#endif

	uint32_t get_tfs_num_msg_to_send(void)
	{
		const hop_distance_t distance = get_dist_to_pull_back();

		simdbgverbose("stdout", "get_tfs_num_msg_to_send=%u, (Dsrc=%d, Dsink=%d, Dss=%d)\n",
			distance, source_distance, sink_distance, sink_source_distance);

		return distance;
	}

	uint32_t get_tfs_duration(void)
	{
		const uint32_t duration = SOURCE_PERIOD_MS;

		//simdbgverbose("stdout", "get_tfs_duration=%u (sink_distance=%d)\n", duration, sink_distance);

		return duration;
	}

	uint32_t get_tfs_period(void)
	{
		const uint32_t duration = get_tfs_duration();
		const uint32_t msg = get_tfs_num_msg_to_send();
		const uint32_t period = duration / msg;

		const uint32_t result_period = period;

		//simdbg("stdout", "get_tfs_period=%" PRIu32 "\n", result_period);

		return result_period;
	}

	uint32_t get_pfs_period(void)
	{
		const uint32_t result_period = scale32(SOURCE_PERIOD_MS, fake_rcv_ratio, UINT16_MAX);

		//simdbg("stdout", "get_pfs_period=%" PRIu32 "\n", result_period);

		return result_period;
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

		choose_rtx_limit = UINT8_MAX;

		sink_received_choose_reponse = FALSE;
		seen_pfs = FALSE;
		is_pfs_candidate = FALSE;

		first_source_distance = UNKNOWN_HOP_DISTANCE;

		away_messages_to_send = SINK_AWAY_MESSAGES_TO_SEND;

		fake_rcv_ratio = UINT16_MAX;

		algorithm = UnknownAlgorithm;

		sequence_number_init(&away_sequence_counter);
		sequence_number_init(&choose_sequence_counter);
		sequence_number_init(&fake_sequence_counter);
		sequence_number_init(&notify_sequence_counter);

		source_fake_sequence_increments = 0;
		sequence_number_init(&source_fake_sequence_counter);

		send_choose_on_next_send_done = FALSE;
		send_fake_on_next_send_done = FALSE;

		call MessageType.register_pair(NORMAL_CHANNEL, "Normal");
		call MessageType.register_pair(AWAY_CHANNEL, "Away");
		call MessageType.register_pair(CHOOSE_CHANNEL, "Choose");
		call MessageType.register_pair(FAKE_CHANNEL, "Fake");
		call MessageType.register_pair(NOTIFY_CHANNEL, "Notify");

		call NodeType.register_pair(SourceNode, "SourceNode");
		call NodeType.register_pair(SinkNode, "SinkNode");
		call NodeType.register_pair(NormalNode, "NormalNode");
		call NodeType.register_pair(TempFakeNode, "TempFakeNode");
		call NodeType.register_pair(PermFakeNode, "PermFakeNode");

		if (call NodeType.is_node_sink())
		{
			call NodeType.init(SinkNode);

			sink_distance = 0;

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

	task void send_choose_message_task();
	task void send_fake_message_task();

	void send_any_done(message_t* msg, error_t error)
	{
		if (!busy)
		{
			if (send_choose_on_next_send_done)
			{
				post send_choose_message_task();
				send_choose_on_next_send_done = FALSE;
			}

			if (send_fake_on_next_send_done)
			{
				post send_fake_message_task();
				send_fake_on_next_send_done = FALSE;
			}
		}
	}

	USE_MESSAGE_NO_EXTRA_TO_SEND(Normal);
	USE_MESSAGE_WITH_CALLBACK_NO_EXTRA_TO_SEND(Away);
	USE_MESSAGE_WITH_CALLBACK_NO_EXTRA_TO_SEND(Choose);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Fake);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Notify);

	event void ObjectDetector.detect()
	{
		// A sink node cannot become a source node
		if (call NodeType.get() != SinkNode)
		{
			call NodeType.set(SourceNode);

			call BroadcastNormalTimer.startPeriodic(SOURCE_PERIOD_MS);

			first_source_distance = 0;
			source_distance = 0;

			{
				NotifyMessage message;
				message.source_id = TOS_NODE_ID;
				message.sequence_number = sequence_number_next(&notify_sequence_counter);
				message.source_distance = 0;
				message.source_period = SOURCE_PERIOD_MS;

				if (send_Notify_message(&message, AM_BROADCAST_ADDR))
				{
					sequence_number_increment(&notify_sequence_counter);
				}
			}

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

	void become_Fake(const ChooseMessage* message, uint8_t fake_type, uint32_t become_fake_time)
	{
#ifdef SLP_VERBOSE_DEBUG
		assert(fake_type == PermFakeNode || fake_type == TempFakeNode);
#endif

		// Stop any existing fake message generation.
		// This is necessary when transitioning from TempFS to TailFS.
		call FakeMessageGenerator.stop();

		call NodeType.set(fake_type);

		switch (fake_type)
		{
		case PermFakeNode:
			call FakeMessageGenerator.start(message, sizeof(*message), become_fake_time);
			break;

		case TempFakeNode:
			call FakeMessageGenerator.startLimited(message, sizeof(*message), get_tfs_duration(), become_fake_time);
			break;

		default:
			__builtin_unreachable();
		}
	}

	void decide_not_pfs_candidate(uint16_t max_hop)
	{
		if (is_pfs_candidate && first_source_distance != UNKNOWN_HOP_DISTANCE && max_hop > hop_distance_increment(first_source_distance))
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
			return max(first_source_distance, max_hop);
		}
	}

	event void BroadcastNormalTimer.fired()
	{
		NormalMessage message;

		simdbgverbose("SourceBroadcasterC", "BroadcastNormalTimer fired.\n");

		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;
		message.max_hop = (sink_source_distance != UNKNOWN_HOP_DISTANCE) ? sink_source_distance : 0;
		message.sink_source_distance = sink_source_distance;
		message.fake_rcv_ratio = scale32(UINT16_MAX, source_fake_sequence_increments + 1, sequence_number_get(&fake_sequence_counter) + 1);

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
		message.max_hop = new_max_hop((sink_source_distance != UNKNOWN_HOP_DISTANCE) ? sink_source_distance : 0);

#ifdef SPACE_BEHIND_SINK
		message.algorithm = GenericAlgorithm;
#else
		message.algorithm = FurtherAlgorithm;
#endif

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

	ChooseMessage choose_message;

	task void send_choose_message_task()
	{
		error_t error = send_Choose_message_ex(&choose_message, AM_BROADCAST_ADDR);

		if (error != SUCCESS)
		{
			if (!busy)
			{
				post send_choose_message_task();
			}
			else
			{
				send_choose_on_next_send_done = TRUE;
			}
		}
	}

	void request_next_fake_source()
	{
		choose_rtx_limit = (call NodeType.get() == TempFakeNode || call NodeType.get() == PermFakeNode)
			? CHOOSE_RTX_LIMIT_FOR_FS
			: UINT8_MAX;

		choose_message.sequence_number = sequence_number_next(&choose_sequence_counter);
		choose_message.source_id = TOS_NODE_ID;
		choose_message.sink_distance = sink_distance;
		choose_message.sink_source_distance = sink_source_distance;
		
#ifdef SPACE_BEHIND_SINK
		choose_message.algorithm = GenericAlgorithm;
#else
		choose_message.algorithm = FurtherAlgorithm;
#endif

		post send_choose_message_task();

		sequence_number_increment(&choose_sequence_counter);
	}

	bool set_first_source_distance(hop_distance_t msg_source_distance)
	{
		if (first_source_distance == UNKNOWN_HOP_DISTANCE)
		{
			first_source_distance = hop_distance_increment(msg_source_distance);
			call Leds.led1On();
			is_pfs_candidate = TRUE;

			//call BeaconSenderTimer.startOneShot(beacon_send_wait());

			return TRUE;
		}

		return FALSE;
	}

	void Normal_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		decide_not_pfs_candidate(rcvd->max_hop);

		source_distance = hop_distance_min(source_distance, hop_distance_increment(rcvd->source_distance));
		sink_source_distance = hop_distance_min(sink_source_distance, rcvd->sink_source_distance);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			fake_rcv_ratio = rcvd->fake_rcv_ratio;

			set_first_source_distance(rcvd->source_distance);

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.source_distance += 1;
			forwarding_message.max_hop = new_max_hop(rcvd->max_hop);

			send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Sink_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		source_distance = hop_distance_min(source_distance, hop_distance_increment(rcvd->source_distance));
		sink_source_distance = hop_distance_min(sink_source_distance, hop_distance_increment(rcvd->source_distance));

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			fake_rcv_ratio = rcvd->fake_rcv_ratio;

			if (set_first_source_distance(rcvd->source_distance))
			{
				// Forward on the normal message to help set up
				// good distances for nodes around the source
				NormalMessage forwarding_message = *rcvd;
				forwarding_message.sink_source_distance = sink_source_distance;
				forwarding_message.source_distance += 1;
				forwarding_message.max_hop = new_max_hop(rcvd->max_hop);

				send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
			}

			// Keep sending choose messages until we get a valid response
			if (!sink_received_choose_reponse)
			{
				request_next_fake_source();
			}
		}
	}

	void Fake_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		source_distance = hop_distance_min(source_distance, hop_distance_increment(rcvd->source_distance));
		sink_source_distance = hop_distance_min(sink_source_distance, rcvd->sink_source_distance);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			fake_rcv_ratio = rcvd->fake_rcv_ratio;

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.source_distance += 1;
			forwarding_message.max_hop = new_max_hop(rcvd->max_hop);

			send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SinkNode: Sink_receive_Normal(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Normal(rcvd, source_addr); break;
		case TempFakeNode:
		case PermFakeNode:
			Fake_receive_Normal(rcvd, source_addr); break;
		case SourceNode: break;
	RECEIVE_MESSAGE_END(Normal)

	void Source_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_distance = sink_source_distance = hop_distance_min(sink_source_distance, rcvd->sink_distance + 1);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;

			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Normal_receive_Away(message_t* msg, const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		decide_not_pfs_candidate(rcvd->max_hop);

		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_distance = hop_distance_min(sink_distance, hop_distance_increment(rcvd->sink_distance));

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;
			forwarding_message.max_hop = new_max_hop(rcvd->max_hop);

			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Fake_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		decide_not_pfs_candidate(rcvd->max_hop);

		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_distance = hop_distance_min(sink_distance, hop_distance_increment(rcvd->sink_distance));

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;
			forwarding_message.max_hop = new_max_hop(rcvd->max_hop);

			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Away, Receive)
		case SourceNode: Source_receive_Away(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Away(msg, rcvd, source_addr); break;

		case PermFakeNode:
		case TempFakeNode: Fake_receive_Away(rcvd, source_addr); break;

		case SinkNode: break;
	RECEIVE_MESSAGE_END(Away)

	void send_Away_done(message_t* msg, error_t error)
	{
		if (error == SUCCESS)
		{
			if (call NodeType.get() == SinkNode)
			{
				away_messages_to_send -= 1;

				if (away_messages_to_send > 0)
				{
					call AwaySenderTimer.startOneShot(AWAY_DELAY_MS);
				}
			}
		}
		else
		{
			call AwaySenderTimer.startOneShot(AWAY_DELAY_MS);
		}
	}


	void Sink_receive_Choose(const ChooseMessage* const rcvd, am_addr_t source_addr)
	{
		sink_received_choose_reponse = TRUE;
	}

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
		sink_distance = hop_distance_min(sink_distance, hop_distance_increment(rcvd->sink_distance));

#ifdef SLP_VERBOSE_DEBUG
		if (!should_process_choose())
		{
			simdbgverbose("stdout", "Dropping choose and not becoming FS because of should_process_choose() (dss=%d, ds=%d)\n",
				min_sink_source_distance, min_source_distance);
		}
#endif

		if (sequence_number_before(&choose_sequence_counter, rcvd->sequence_number) && should_process_choose())
		{
			sequence_number_update(&choose_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_CHOOSE(rcvd);

			if (is_pfs_candidate && rcvd->sink_distance > 0)
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
		case SinkNode: Sink_receive_Choose(rcvd, source_addr); break;

		case SourceNode:
		case TempFakeNode:
		case PermFakeNode: break;
	RECEIVE_MESSAGE_END(Choose)

	void send_Choose_done(message_t* msg, error_t error)
	{
		if (choose_rtx_limit != UINT8_MAX)
		{
			choose_rtx_limit -= 1;

			if (choose_rtx_limit != 0)
			{
				post send_choose_message_task();
			}
		}	
	}

	void Sink_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		sink_received_choose_reponse = TRUE;

		sink_source_distance = hop_distance_min(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

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
			source_fake_sequence_increments += 1;

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

			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.max_hop = new_max_hop(rcvd->max_hop);

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Fake_receive_Fake(message_t* msg, const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		const bool is_new = sequence_number_before_and_update(&fake_sequence_counter, rcvd->sequence_number);

		const uint32_t receive_fake_time = call PacketTimeStamp.isValid(msg)
			? call PacketTimeStamp.timestamp(msg)
			: call LocalTime.get();

		decide_not_pfs_candidate(rcvd->max_hop);

		sink_source_distance = hop_distance_min(sink_source_distance, rcvd->sink_source_distance);

		if (is_new)
		{
			FakeMessage forwarding_message = *rcvd;

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


	void x_receive_Notify(const NotifyMessage* const rcvd, am_addr_t source_addr)
	{
		const bool is_new = sequence_number_before_and_update(&notify_sequence_counter, rcvd->sequence_number);

		//source_period_ms = rcvd->source_period;

		if (is_new)
		{
			NotifyMessage forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;

			METRIC_RCV_NOTIFY(rcvd);

			send_Notify_message(&forwarding_message, AM_BROADCAST_ADDR);

			set_first_source_distance(rcvd->source_distance);
		}
	}

	void Sink_receive_Notify(const NotifyMessage* const rcvd, am_addr_t source_addr)
	{
		x_receive_Notify(rcvd, source_addr);

		// Keep sending away messages until we get a valid response
		if (!sink_received_choose_reponse)
		{
			request_next_fake_source();
		}
	}

	RECEIVE_MESSAGE_BEGIN(Notify, Receive)
		case SinkNode: Sink_receive_Notify(rcvd, source_addr); break;

		case SourceNode:
		case NormalNode:
		case TempFakeNode:
		case PermFakeNode: x_receive_Notify(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Notify)


	event uint32_t FakeMessageGenerator.initialStartDelay()
	{
		// The first fake message is to be sent half way through the period.
		// After this message is sent, all other messages are sent with an interval
		// of the period given. The aim here is to reduce the traffic at the start and
		// end of the TFS duration.
		//return signal FakeMessageGenerator.calculatePeriod() / 4;
		return get_tfs_period() / 4;
	}

	event uint32_t FakeMessageGenerator.calculatePeriod()
	{
		switch (call NodeType.get())
		{
		case PermFakeNode: return get_pfs_period();
		case TempFakeNode: return get_tfs_period();
		default:
			ERROR_OCCURRED(ERROR_CALLED_FMG_CALC_PERIOD_ON_NON_FAKE_NODE,
				"Called FakeMessageGenerator.calculatePeriod on non-fake node.\n");
			return 0;
		}
	}

	task void send_fake_message_task()
	{
		signal FakeMessageGenerator.sendFakeMessage();
	}

	event void FakeMessageGenerator.sendFakeMessage()
	{
		error_t error;

		FakeMessage message;
		message.sequence_number = sequence_number_next(&fake_sequence_counter);
		message.sink_source_distance = sink_source_distance;
		message.sender_source_distance = source_distance;
		message.max_hop = new_max_hop(0);
		message.sink_distance = sink_distance;
		message.from_pfs = (call NodeType.get() == PermFakeNode);
		message.source_id = TOS_NODE_ID;

		error = send_Fake_message_ex(&message, AM_BROADCAST_ADDR);

		if (error == SUCCESS)
		{
			sequence_number_increment(&fake_sequence_counter);
		}
		else
		{
			if (!busy)
			{
				post send_fake_message_task();
			}
			else
			{
				send_fake_on_next_send_done = TRUE;
			}
		}
	}

	event void FakeMessageGenerator.durationExpired(const void* original_message, uint8_t original_size, uint32_t duration_expired_at)
	{
		//assert(sizeof(choose_message) == original_size);

		choose_message = *(const ChooseMessage*)original_message;
		choose_message.sink_source_distance = sink_source_distance;
        choose_message.sink_distance += 1;

		simdbgverbose("stdout", "Finished sending Fake from TFS, now sending Choose.\n");

		// When finished sending fake messages from a TFS

		post send_choose_message_task();

		become_Normal();
	}
}
