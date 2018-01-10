#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"
#include "NeighbourDetail.h"
#include "HopDistance.h"

#include "AwayMessage.h"
#include "ChooseMessage.h"
#include "FakeMessage.h"
#include "NormalMessage.h"
#include "BeaconMessage.h"
#include "NotifyMessage.h"

#include "lpl/SLPDutyCycleFlags.h"

#include <Timer.h>
#include <TinyError.h>
#include <scale.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, hop_distance_increment(msg->source_distance))
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, hop_distance_increment(msg->sink_distance))
#define METRIC_RCV_CHOOSE(msg) METRIC_RCV(Choose, source_addr, msg->source_id, msg->sequence_number, hop_distance_increment(msg->sink_distance))
#define METRIC_RCV_FAKE(msg) METRIC_RCV(Fake, source_addr, msg->source_id, msg->sequence_number, UNKNOWN_HOP_DISTANCE)
#define METRIC_RCV_BEACON(msg) METRIC_RCV(Beacon, source_addr, AM_BROADCAST_ADDR, UNKNOWN_SEQNO, UNKNOWN_HOP_DISTANCE)
#define METRIC_RCV_NOTIFY(msg) METRIC_RCV(Notify, source_addr, msg->source_id, msg->sequence_number, hop_distance_increment(msg->source_distance))

#define AWAY_DELAY_MS (SOURCE_PERIOD_MS / 4)

typedef struct
{
	hop_distance_t source_distance;
} distance_container_t;

void distance_update(distance_container_t* find, distance_container_t const* given)
{
	find->source_distance = hop_distance_min(find->source_distance, given->source_distance);
}

void distance_print(const char* name, size_t i, am_addr_t address, distance_container_t const* contents)
{
#ifdef TOSSIM
	simdbg_clear(name, "[%u] => addr=%u / dist=%d",
		i, address, contents->source_distance);
#endif
}

DEFINE_NEIGHBOUR_DETAIL(distance_container_t, distance, distance_update, distance_print, SLP_MAX_1_HOP_NEIGHBOURHOOD);

#define UPDATE_NEIGHBOURS(addr, source_distance) \
{ \
	const distance_container_t dist = { source_distance }; \
	insert_distance_neighbour(&neighbours, addr, &dist); \
}

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;
	uses interface Random;
	uses interface Crc;

	uses interface Timer<TMilli> as BroadcastNormalTimer;
	uses interface Timer<TMilli> as AwaySenderTimer;
	uses interface Timer<TMilli> as BeaconSenderTimer;

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
	uses interface Receive as ChooseSnoop;
	uses interface PacketAcknowledgements as ChoosePacketAcknowledgements;

	uses interface AMSend as FakeSend;
	uses interface Receive as FakeReceive;

	uses interface AMSend as BeaconSend;
	uses interface Receive as BeaconReceive;

	uses interface AMSend as NotifySend;
	uses interface Receive as NotifyReceive;

	uses interface MetricLogging;
	uses interface MetricHelpers;

	uses interface NodeType;
	uses interface MessageType;
	uses interface FakeMessageGenerator;
	uses interface ObjectDetector;

	uses interface SequenceNumbers as NormalSeqNos;

	uses interface SLPDutyCycle;
}

implementation
{
#ifdef SLP_DEBUG
	#include "HopDistanceDebug.h"
#endif

	distance_neighbours_t neighbours;

	SequenceNumber away_sequence_counter;
	SequenceNumber choose_sequence_counter;
	SequenceNumber fake_sequence_counter;
	SequenceNumber notify_sequence_counter;

	SequenceNumber source_fake_sequence_counter;
	uint32_t source_fake_sequence_increments;

	uint32_t source_period_ms;

	uint8_t fake_count; // Number of fake messages sent in one duration

	hop_distance_t sink_distance;

	bool sink_received_choose_reponse;
	uint8_t choose_rtx_limit;

	hop_distance_t first_source_distance;

	uint8_t away_messages_to_send;

	typedef enum
	{
		UnknownAlgorithm, GenericAlgorithm, FurtherAlgorithm
	} Algorithm;

	Algorithm algorithm;

	uint16_t random_interval(uint16_t min, uint16_t max)
	{
		return min + call Random.rand16() / (UINT16_MAX / (max - min + 1) + 1);
	}

	bool pfs_can_become_normal(void)
	{
		switch (algorithm)
		{
		case GenericAlgorithm:  return TRUE;
		case FurtherAlgorithm:  return FALSE;
		default:                return FALSE;
		}
	}

	uint32_t get_dist_to_pull_back(void)
	{
#if defined(PB_FIXED2_APPROACH)
		return 2;

#elif defined(PB_FIXED1_APPROACH)
		return 1;

#elif defined(PB_RND_APPROACH)
		return 1 + (call Random.rand16() % 2);

#else
#   error "Technique not specified"
#endif
	}

	uint32_t get_tfs_num_msg_to_send(void)
	{
		const uint32_t distance = get_dist_to_pull_back();

		//simdbgverbose("stdout", "get_tfs_num_msg_to_send=%u, (Dsrc=%d, Dsink=%d, Dss=%d)\n",
		//  distance, source_distance, sink_distance, sink_source_distance);

		return distance;
	}

	uint32_t get_tfs_duration(void)
	{
		const uint32_t duration = SOURCE_PERIOD_MS;

		/*if (sink_distance == UNKNOWN_HOP_DISTANCE || sink_distance <= 1)
		{
			duration -= AWAY_DELAY_MS;
		}

		simdbgverbose("stdout", "get_tfs_duration=%u (sink_distance=%d)\n", duration, sink_distance);*/

		return duration;
	}

	uint32_t get_tfs_period(void)
	{
		const uint32_t duration = get_tfs_duration();
		const uint32_t msg = get_tfs_num_msg_to_send();
		const uint32_t period = duration / msg;

		const uint32_t result_period = period;

		//simdbgverbose("stdout", "get_tfs_period=%u\n", result_period);

		return result_period;
	}

	uint32_t get_pfs_period(void)
	{
		// Need to add one here because it is possible for the values to both be 0
		// if no fake messages have ever been received.
		const uint32_t seq_inc = source_fake_sequence_increments + 1;
		const uint32_t counter = sequence_number_get(&source_fake_sequence_counter) + 1;

		// result_period = SOURCE_PERIOD_MS * (seq_inc/counter) // accounts for overflow
		const uint32_t result_period = scale32(SOURCE_PERIOD_MS, seq_inc, counter);

		ASSERT_MESSAGE(seq_inc <= counter, "Seen more fake than has been generated.");

		// The double version:
		/*const double ratio = seq_inc / (double)counter;
		const uint32_t result_period2 = ceil(SOURCE_PERIOD_MS * ratio);
		simdbgverbose("stdout", "get_pfs_period=%u, %u (sent=%u, rcvd=%u, x=%f)\n",
		  result_period, result_period2, counter, seq_inc, ratio);*/

		return result_period;
	}

	am_addr_t fake_walk_target(void)
	{
		am_addr_t chosen_address;

		distance_neighbours_t local_neighbours;
		init_distance_neighbours(&local_neighbours);

		if (first_source_distance != UNKNOWN_HOP_DISTANCE)
		{
			uint16_t i;
			for (i = 0; i != neighbours.size; ++i)
			{
				distance_neighbour_detail_t const* const neighbour = &neighbours.data[i];

				if (neighbour->contents.source_distance >= first_source_distance)
				{
					insert_distance_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
				}
			}
		}

		if (local_neighbours.size == 0)
		{
			simdbgverbose("stdout", "No local neighbours to choose so broadcasting. (my-dist=%d, my-neighbours-size=%u)\n",
				landmark_distance, neighbours.size);

			chosen_address = AM_BROADCAST_ADDR;
		}
		else
		{
			// Choose a neighbour with equal probabilities.
			const uint16_t rnd = call Random.rand16();
			const uint16_t neighbour_index = rnd % local_neighbours.size;
			const distance_neighbour_detail_t* const neighbour = &local_neighbours.data[neighbour_index];

			chosen_address = neighbour->address;

#ifdef SLP_VERBOSE_DEBUG
			print_distance_neighbours("stdout", &local_neighbours);
#endif

			simdbgverbose("stdout", "Chosen %u at index %u (rnd=%u) out of %u neighbours (their-dist=%d my-dist=%d)\n",
				chosen_address, neighbour_index, rnd, local_neighbours.size,
				neighbour->contents.distance, landmark_distance);
		}

		return chosen_address;
	}

	bool busy;
	message_t packet;

	event void Boot.booted()
	{
		busy = FALSE;
		call Packet.clear(&packet);

		source_period_ms = UINT32_MAX;

		sink_distance = UNKNOWN_HOP_DISTANCE;

		sink_received_choose_reponse = FALSE;
		choose_rtx_limit = UINT8_MAX;

		first_source_distance = UNKNOWN_HOP_DISTANCE;

		away_messages_to_send = 3;

		algorithm = UnknownAlgorithm;

		init_distance_neighbours(&neighbours);

		sequence_number_init(&away_sequence_counter);
		sequence_number_init(&choose_sequence_counter);
		sequence_number_init(&fake_sequence_counter);
		sequence_number_init(&notify_sequence_counter);

		source_fake_sequence_increments = 0;
		sequence_number_init(&source_fake_sequence_counter);

		call MessageType.register_pair(NORMAL_CHANNEL, "Normal");
		call MessageType.register_pair(AWAY_CHANNEL, "Away");
		call MessageType.register_pair(CHOOSE_CHANNEL, "Choose");
		call MessageType.register_pair(FAKE_CHANNEL, "Fake");
		call MessageType.register_pair(BEACON_CHANNEL, "Beacon");
		call MessageType.register_pair(NOTIFY_CHANNEL, "Notify");

		call NodeType.register_pair(SourceNode, "SourceNode");
		call NodeType.register_pair(SinkNode, "SinkNode");
		call NodeType.register_pair(NormalNode, "NormalNode");
		call NodeType.register_pair(TempFakeNode, "TempFakeNode");
		call NodeType.register_pair(PermFakeNode, "PermFakeNode");
		call NodeType.register_pair(TailFakeNode, "TailFakeNode");

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


	USE_MESSAGE_NO_EXTRA_TO_SEND(Normal);
	USE_MESSAGE_WITH_CALLBACK_NO_EXTRA_TO_SEND(Away);
	USE_MESSAGE_ACK_REQUEST_WITH_CALLBACK(Choose);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Fake);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Beacon);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Notify);

	event void ObjectDetector.detect()
	{
		// A sink node cannot become a source node
		if (call NodeType.get() != SinkNode)
		{
			call NodeType.set(SourceNode);

			call BroadcastNormalTimer.startPeriodic(SOURCE_PERIOD_MS);

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
		}
	}

	uint32_t beacon_send_wait(void)
	{
		return 45U + random_interval(0, 50);
	}

	void become_Normal(void)
	{
		call FakeMessageGenerator.stop();

		call NodeType.set(NormalNode);
	}

	void become_Fake(const ChooseMessage* message, uint8_t fake_type, uint32_t become_fake_time)
	{
#ifdef SLP_VERBOSE_DEBUG
		assert(fake_type == PermFakeNode || fake_type == TempFakeNode || fake_type == TailFakeNode);
#endif

		// Stop any existing fake message generation.
		// This is necessary when transitioning from TempFS to TailFS.
		call FakeMessageGenerator.stop();

		call NodeType.set(fake_type);

		fake_count = 0;

		switch (fake_type)
		{
		case PermFakeNode:
			call FakeMessageGenerator.start(message, sizeof(*message), become_fake_time);
			break;

		case TailFakeNode:
			call FakeMessageGenerator.startRepeated(message, sizeof(*message), get_tfs_duration(), become_fake_time);
			break;

		case TempFakeNode:
			call FakeMessageGenerator.startLimited(message, sizeof(*message), get_tfs_duration(), become_fake_time);
			break;

		default:
			__builtin_unreachable();
		}
	}

	void possibly_become_Normal(uint8_t message_type, hop_distance_t ultimate_sender_first_source_distance, am_addr_t source_id)
	{
		const uint8_t type = call NodeType.get();

		const bool source_type_perm_or_tail = (message_type == PermFakeNode) | (message_type == TailFakeNode);

		if ((
				(source_type_perm_or_tail && type == PermFakeNode && pfs_can_become_normal()) ||
				(source_type_perm_or_tail && type == TailFakeNode)
			) &&
			(
				ultimate_sender_first_source_distance != UNKNOWN_HOP_DISTANCE &&
				first_source_distance != UNKNOWN_HOP_DISTANCE
			) &&
			(
				ultimate_sender_first_source_distance > first_source_distance ||
				(ultimate_sender_first_source_distance == first_source_distance && source_id > TOS_NODE_ID)
			))
		{
			// Stop fake & choose sending and become a normal node
			become_Normal();
		}
	}

	event void BroadcastNormalTimer.fired()
	{
		NormalMessage message;

		simdbgverbose("SourceBroadcasterC", "BroadcastNormalTimer fired.\n");

		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;

		message.fake_sequence_number = sequence_number_get(&fake_sequence_counter);
		message.fake_sequence_increments = source_fake_sequence_increments;

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

	bool any_further_neighbours()
	{
		uint16_t i;
		bool any_further = TRUE;

		if (first_source_distance == UNKNOWN_HOP_DISTANCE || neighbours.size == 0)
		{
			return FALSE;
		}

		// If all neighbours are closer to the sink, we need
		// to ask all neighbours to become a TFS
		for (i = 0; i != neighbours.size; ++i)
		{
			const hop_distance_t neighbour_source_distance = neighbours.data[i].contents.source_distance;

			any_further &= (neighbour_source_distance >= first_source_distance);
		}

		return any_further;
	}

	task void request_next_fake_source_task()
	{
		const am_addr_t target = fake_walk_target();

		bool ack_request = target != AM_BROADCAST_ADDR;

		ChooseMessage message;
		message.sequence_number = sequence_number_next(&choose_sequence_counter);
		message.source_id = TOS_NODE_ID;
		message.sink_distance = 0;
		
#ifdef SPACE_BEHIND_SINK
		message.algorithm = GenericAlgorithm;
#else
		message.algorithm = FurtherAlgorithm;
#endif

		message.any_further = any_further_neighbours();

		message.ultimate_sender_first_source_distance = first_source_distance;
		message.source_node_type = call NodeType.get();

		if (send_Choose_message(&message, target, &ack_request))
		{
			sequence_number_increment(&choose_sequence_counter);
		}
		else
		{
			post request_next_fake_source_task();
		}
	}

	void request_next_fake_source()
	{
		choose_rtx_limit = (call NodeType.get() == TempFakeNode || call NodeType.get() == TailFakeNode || call NodeType.get() == PermFakeNode)
			? CHOOSE_RTX_LIMIT_FOR_FS
			: UINT8_MAX;
		post request_next_fake_source_task();
	}

	event void BeaconSenderTimer.fired()
	{
		BeaconMessage message;
		bool result;

		simdbgverbose("SourceBroadcasterC", "BeaconSenderTimer fired.\n");

		if (busy)
		{
			simdbgverbose("stdout", "Device is busy rescheduling beacon\n");
			call BeaconSenderTimer.startOneShot(beacon_send_wait());
			return;
		}

		message.source_distance_of_sender = first_source_distance;
		message.source_period = source_period_ms;

		call Packet.clear(&packet);

		result = send_Beacon_message(&message, AM_BROADCAST_ADDR);
		if (!result)
		{
			simdbgverbose("stdout", "Send failed rescheduling beacon\n");
			call BeaconSenderTimer.startOneShot(beacon_send_wait());
		}
	}

	bool set_first_source_distance(hop_distance_t source_distance)
	{
		if (first_source_distance == UNKNOWN_HOP_DISTANCE)
		{
			first_source_distance = hop_distance_increment(source_distance);
			call Leds.led1On();

			call BeaconSenderTimer.startOneShot(beacon_send_wait());

			return TRUE;
		}

		return FALSE;
	}

	void Source_receive_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr, uint32_t rcvd_timestamp)
	{
		const bool is_new = call NormalSeqNos.before_and_update(rcvd->source_id, rcvd->sequence_number);

		const uint8_t duty_cycle_flags =
			(is_new ? SLP_DUTY_CYCLE_IS_NEW : 0) |
			(call PacketTimeStamp.isValid(msg) ? SLP_DUTY_CYCLE_VALID_TIMESTAMP : 0);

		UPDATE_NEIGHBOURS(source_addr, 1);

		call SLPDutyCycle.received_Normal(msg, rcvd, duty_cycle_flags, SourceNode, rcvd_timestamp);
	}


	void Normal_receive_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr, uint32_t rcvd_timestamp)
	{
		const bool is_new = call NormalSeqNos.before_and_update(rcvd->source_id, rcvd->sequence_number);

		const uint8_t duty_cycle_flags =
			(is_new ? SLP_DUTY_CYCLE_IS_NEW : 0) |
			(call PacketTimeStamp.isValid(msg) ? SLP_DUTY_CYCLE_VALID_TIMESTAMP : 0);

		call SLPDutyCycle.received_Normal(msg, rcvd, duty_cycle_flags, SourceNode, rcvd_timestamp);

		UPDATE_NEIGHBOURS(source_addr, rcvd->source_distance);

		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (is_new)
		{
			NormalMessage forwarding_message;

			METRIC_RCV_NORMAL(rcvd);

			set_first_source_distance(rcvd->source_distance);

			forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;
			forwarding_message.fake_sequence_number = source_fake_sequence_counter;
			forwarding_message.fake_sequence_increments = source_fake_sequence_increments;

			send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Sink_receive_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr, uint32_t rcvd_timestamp)
	{
		const bool is_new = call NormalSeqNos.before_and_update(rcvd->source_id, rcvd->sequence_number);

		const uint8_t duty_cycle_flags =
			(is_new ? SLP_DUTY_CYCLE_IS_NEW : 0) |
			(call PacketTimeStamp.isValid(msg) ? SLP_DUTY_CYCLE_VALID_TIMESTAMP : 0);

		call SLPDutyCycle.received_Normal(msg, rcvd, duty_cycle_flags, SourceNode, rcvd_timestamp);

		UPDATE_NEIGHBOURS(source_addr, rcvd->source_distance);

		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (is_new)
		{
			METRIC_RCV_NORMAL(rcvd);

			if (set_first_source_distance(rcvd->source_distance))
			{
				// Having the sink forward the normal message helps set up
				// the source distance gradients.
				// However, we don't want to keep doing this as it benefits the attacker.
				NormalMessage forwarding_message = *rcvd;
				forwarding_message.source_distance += 1;
				forwarding_message.fake_sequence_number = source_fake_sequence_counter;
				forwarding_message.fake_sequence_increments = source_fake_sequence_increments;

				send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
			}

			// Keep sending away messages until we get a valid response
			if (!sink_received_choose_reponse)
			{
				request_next_fake_source();
			}
		}
	}

	void Fake_receive_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr, uint32_t rcvd_timestamp)
	{
		const bool is_new = call NormalSeqNos.before_and_update(rcvd->source_id, rcvd->sequence_number);

		const uint8_t duty_cycle_flags =
			(is_new ? SLP_DUTY_CYCLE_IS_NEW : 0) |
			(call PacketTimeStamp.isValid(msg) ? SLP_DUTY_CYCLE_VALID_TIMESTAMP : 0);

		call SLPDutyCycle.received_Normal(msg, rcvd, duty_cycle_flags, SourceNode, rcvd_timestamp);

		UPDATE_NEIGHBOURS(source_addr, rcvd->source_distance);

		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (is_new)
		{
			NormalMessage forwarding_message;

			METRIC_RCV_NORMAL(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;
			forwarding_message.fake_sequence_number = source_fake_sequence_counter;
			forwarding_message.fake_sequence_increments = source_fake_sequence_increments;

			send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	RECEIVE_MESSAGE_WITH_TIMESTAMP_BEGIN(Normal, Receive)
		case SourceNode: Source_receive_Normal(msg, rcvd, source_addr, rcvd_timestamp); break;
		case SinkNode: Sink_receive_Normal(msg, rcvd, source_addr, rcvd_timestamp); break;
		case NormalNode: Normal_receive_Normal(msg, rcvd, source_addr, rcvd_timestamp); break;
		case TempFakeNode:
		case TailFakeNode:
		case PermFakeNode: Fake_receive_Normal(msg, rcvd, source_addr, rcvd_timestamp); break;
	RECEIVE_MESSAGE_END(Normal)


	void Source_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		if (sequence_number_before_and_update(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			METRIC_RCV_AWAY(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;

			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Normal_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		if (sequence_number_before_and_update(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			METRIC_RCV_AWAY(rcvd);

			sink_distance = hop_distance_min(sink_distance, hop_distance_increment(rcvd->sink_distance));

			forwarding_message = *rcvd;
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;

			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Fake_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		if (sequence_number_before_and_update(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			METRIC_RCV_AWAY(rcvd);

			sink_distance = hop_distance_min(sink_distance, hop_distance_increment(rcvd->sink_distance));

			forwarding_message = *rcvd;
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;

			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Away, Receive)
		case SinkNode: break;
		case SourceNode: Source_receive_Away(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Away(rcvd, source_addr); break;

		case TailFakeNode:
		case PermFakeNode:
		case TempFakeNode: Fake_receive_Away(rcvd, source_addr); break;
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

	void x_snoop_Choose(const ChooseMessage* const rcvd, am_addr_t source_addr);


	void Sink_receive_Choose(message_t* msg, const ChooseMessage* const rcvd, am_addr_t source_addr)
	{
		sink_received_choose_reponse = TRUE;
	}

	void Normal_receive_Choose(message_t* msg, const ChooseMessage* const rcvd, am_addr_t source_addr)
	{
		const uint32_t become_fake_time = call PacketTimeStamp.isValid(msg)
			? call PacketTimeStamp.timestamp(msg)
			: call BroadcastNormalTimer.getNow();

		x_snoop_Choose(rcvd, source_addr);

		if (sequence_number_before_and_update(&choose_sequence_counter, rcvd->sequence_number))
		{
			METRIC_RCV_CHOOSE(rcvd);

			if (rcvd->sink_distance == 0)
			{
				distance_neighbour_detail_t* neighbour = find_distance_neighbour(&neighbours, source_addr);

				if (!rcvd->any_further ||
					first_source_distance == UNKNOWN_HOP_DISTANCE ||
					neighbour == NULL ||
					neighbour->contents.source_distance == UNKNOWN_HOP_DISTANCE ||
					neighbour->contents.source_distance <= first_source_distance)
				{
					become_Fake(rcvd, TempFakeNode, become_fake_time);
				}
#ifdef SLP_VERBOSE_DEBUG
				else
				{
					if (neighbour == NULL)
					{
						LOG_STDOUT(0, "Normal could have become FAKE but didn't fsd=" HOP_DISTANCE_SPEC ", n=%p\n",
							first_source_distance, neighbour);
					}
					else
					{
						LOG_STDOUT(0, "Normal could have become FAKE but didn't fsd=" HOP_DISTANCE_SPEC ", n=%p, nd=" HOP_DISTANCE_SPEC "\n",
							first_source_distance, neighbour, neighbour->contents.source_distance);
					}
				}
#endif
			}
			else
			{
				const am_addr_t target = fake_walk_target();

				if (target == AM_BROADCAST_ADDR)
				{
					become_Fake(rcvd, PermFakeNode, become_fake_time);
				}
				else
				{
					become_Fake(rcvd, TempFakeNode, become_fake_time);
				}
			}
		}
	}

	void Fake_receive_Choose(message_t* msg, const ChooseMessage* const rcvd, am_addr_t source_addr)
	{
		x_snoop_Choose(rcvd, source_addr);

		possibly_become_Normal(rcvd->source_node_type, rcvd->ultimate_sender_first_source_distance, source_addr);
	}

	RECEIVE_MESSAGE_BEGIN(Choose, Receive)
		case SinkNode: Sink_receive_Choose(msg, rcvd, source_addr); break;
		case NormalNode: Normal_receive_Choose(msg, rcvd, source_addr); break;
		
		case PermFakeNode:
		case TempFakeNode:
		case TailFakeNode: Fake_receive_Choose(msg, rcvd, source_addr); break;

		case SourceNode: break;
	RECEIVE_MESSAGE_END(Choose)


	void x_snoop_Choose(const ChooseMessage* const rcvd, am_addr_t source_addr)
	{
		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_distance = hop_distance_min(sink_distance, hop_distance_increment(rcvd->sink_distance));
	}

	RECEIVE_MESSAGE_BEGIN(Choose, Snoop)
		case SinkNode: Sink_receive_Choose(msg, rcvd, source_addr); break;

		case SourceNode:
		case NormalNode: x_snoop_Choose(rcvd, source_addr); break;

		case PermFakeNode:
		case TempFakeNode:
		case TailFakeNode: Fake_receive_Choose(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Choose)

	void send_Choose_done(message_t* msg, error_t error)
	{
		if (choose_rtx_limit != UINT8_MAX)
		{
			choose_rtx_limit -= 1;
		}

		if (error == SUCCESS)
		{
			const bool ack_requested = call AMPacket.destination(msg) != AM_BROADCAST_ADDR;

			if (ack_requested)
			{
				if (call ChoosePacketAcknowledgements.wasAcked(msg))
				{
					if (call NodeType.get() == SinkNode)
					{
						sink_received_choose_reponse = TRUE;
					}
				}
				else
				{
					if (choose_rtx_limit != 0)
					{
						post request_next_fake_source_task();
					}
				}
			}
		}
		else
		{
			if (choose_rtx_limit != 0)
			{
				post request_next_fake_source_task();
			}
		}
	}


	void process_fake_duty_cycle(message_t* msg, const FakeMessage* const rcvd, bool is_new, uint32_t rcvd_timestamp)
	{
		const uint8_t duty_cycle_flags =
			(is_new ? SLP_DUTY_CYCLE_IS_NEW : 0) |
			(rcvd->ultimate_sender_fake_count == 0 ? SLP_DUTY_CYCLE_IS_FIRST_FAKE : 0) |
			(find_distance_neighbour(&neighbours, rcvd->source_id) != NULL ? SLP_DUTY_CYCLE_IS_ADJACENT_TO_FAKE : 0) |
			(call PacketTimeStamp.isValid(msg) ? SLP_DUTY_CYCLE_VALID_TIMESTAMP : 0);

		call SLPDutyCycle.expected(
			rcvd->ultimate_sender_fake_duration_ms,
			rcvd->ultimate_sender_fake_period_ms,
			rcvd->message_type, rcvd_timestamp);
		call SLPDutyCycle.received_Fake(msg, rcvd, duty_cycle_flags, rcvd->message_type, rcvd_timestamp);
	}

	void Normal_receive_Fake(message_t* msg, const FakeMessage* const rcvd, am_addr_t source_addr, uint32_t rcvd_timestamp)
	{
		const bool is_new = sequence_number_before_and_update(&fake_sequence_counter, rcvd->sequence_number);

		process_fake_duty_cycle(msg, rcvd, is_new, rcvd_timestamp);

		if (is_new)
		{
			FakeMessage forwarding_message = *rcvd;

			METRIC_RCV_FAKE(rcvd);

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Sink_receive_Fake(message_t* msg, const FakeMessage* const rcvd, am_addr_t source_addr, uint32_t rcvd_timestamp)
	{
		sink_received_choose_reponse = TRUE;

		Normal_receive_Fake(msg, rcvd, source_addr, rcvd_timestamp);
	}

	void Source_receive_Fake(message_t* msg, const FakeMessage* const rcvd, am_addr_t source_addr, uint32_t rcvd_timestamp)
	{
		const bool is_new = sequence_number_before_and_update(&fake_sequence_counter, rcvd->sequence_number);

		process_fake_duty_cycle(msg, rcvd, is_new, rcvd_timestamp);

		if (is_new)
		{
			source_fake_sequence_increments += 1;

			METRIC_RCV_FAKE(rcvd);
		}
	}

	void Fake_receive_Fake(message_t* msg, const FakeMessage* const rcvd, am_addr_t source_addr, uint32_t rcvd_timestamp)
	{
		Normal_receive_Fake(msg, rcvd, source_addr, rcvd_timestamp);

		possibly_become_Normal(rcvd->message_type, rcvd->ultimate_sender_first_source_distance, rcvd->source_id);
	}

	RECEIVE_MESSAGE_WITH_TIMESTAMP_BEGIN(Fake, Receive)
		case SinkNode: Sink_receive_Fake(msg, rcvd, source_addr, rcvd_timestamp); break;
		case SourceNode: Source_receive_Fake(msg, rcvd, source_addr, rcvd_timestamp); break;
		case NormalNode: Normal_receive_Fake(msg, rcvd, source_addr, rcvd_timestamp); break;
		case TempFakeNode:
		case TailFakeNode:
		case PermFakeNode: Fake_receive_Fake(msg, rcvd, source_addr, rcvd_timestamp); break;
	RECEIVE_MESSAGE_END(Fake)


	void x_receive_Beacon(const BeaconMessage* const rcvd, am_addr_t source_addr, uint32_t rcvd_timestamp)
	{
		UPDATE_NEIGHBOURS(source_addr, rcvd->source_distance_of_sender);

		METRIC_RCV_BEACON(rcvd);

		call SLPDutyCycle.expected(UINT32_MAX, rcvd->source_period, SourceNode, rcvd_timestamp);

		source_period_ms = rcvd->source_period;

		set_first_source_distance(rcvd->source_distance_of_sender);
	}

	RECEIVE_MESSAGE_WITH_TIMESTAMP_BEGIN(Beacon, Receive)
		case SinkNode:
		case SourceNode:
		case NormalNode:
		case TempFakeNode:
		case TailFakeNode:
		case PermFakeNode: x_receive_Beacon(rcvd, source_addr, rcvd_timestamp); break;
	RECEIVE_MESSAGE_END(Beacon)


	void x_receive_Notify(message_t* msg, const NotifyMessage* const rcvd, am_addr_t source_addr, uint32_t rcvd_timestamp)
	{
		const bool is_new = sequence_number_before_and_update(&notify_sequence_counter, rcvd->sequence_number);

		const uint8_t duty_cycle_flags =
			(is_new ? SLP_DUTY_CYCLE_IS_NEW : 0) |
			(call PacketTimeStamp.isValid(msg) ? SLP_DUTY_CYCLE_VALID_TIMESTAMP : 0);

		UPDATE_NEIGHBOURS(source_addr, rcvd->source_distance);

		source_period_ms = rcvd->source_period;

		call SLPDutyCycle.expected(UINT32_MAX, rcvd->source_period, SourceNode, rcvd_timestamp);
		call SLPDutyCycle.received_Normal(msg, rcvd, duty_cycle_flags, SourceNode, rcvd_timestamp);

		if (is_new)
		{
			NotifyMessage forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;

			METRIC_RCV_NOTIFY(rcvd);

			send_Notify_message(&forwarding_message, AM_BROADCAST_ADDR);

			set_first_source_distance(rcvd->source_distance);
		}
	}

	void Sink_receive_Notify(message_t* msg, const NotifyMessage* const rcvd, am_addr_t source_addr, uint32_t rcvd_timestamp)
	{
		x_receive_Notify(msg, rcvd, source_addr, rcvd_timestamp);

		// Keep sending away messages until we get a valid response
		if (!sink_received_choose_reponse)
		{
			request_next_fake_source();
		}
	}

	RECEIVE_MESSAGE_WITH_TIMESTAMP_BEGIN(Notify, Receive)
		case SinkNode: Sink_receive_Notify(msg, rcvd, source_addr, rcvd_timestamp); break;

		case SourceNode:
		case NormalNode:
		case TempFakeNode:
		case TailFakeNode:
		case PermFakeNode: x_receive_Notify(msg, rcvd, source_addr, rcvd_timestamp); break;
	RECEIVE_MESSAGE_END(Notify)


	event uint32_t FakeMessageGenerator.initialStartDelay()
	{
		// The first fake message is to be sent a quarter way through the period.
		// After this message is sent, all other messages are sent with an interval
		// of the period given. The aim here is to reduce the traffic at the start and
		// end of the TFS duration.
		return signal FakeMessageGenerator.calculatePeriod() / 4;
	}

	event uint32_t FakeMessageGenerator.calculatePeriod()
	{
		switch (call NodeType.get())
		{
		case PermFakeNode:
		case TailFakeNode:
			return get_pfs_period();

		case TempFakeNode:
			return get_tfs_period();

		default:
			ERROR_OCCURRED(ERROR_CALLED_FMG_CALC_PERIOD_ON_NON_FAKE_NODE,
				"Called FakeMessageGenerator.calculatePeriod on non-fake node.\n");
			return 0;
		}
	}

	event void FakeMessageGenerator.sendFakeMessage()
	{
		FakeMessage message;

		message.sequence_number = sequence_number_next(&fake_sequence_counter);
		message.message_type = call NodeType.get();
		message.source_id = TOS_NODE_ID;
		message.ultimate_sender_first_source_distance = first_source_distance;
		message.ultimate_sender_fake_duration_ms = message.message_type == PermFakeNode ? UINT32_MAX : get_tfs_duration();
		message.ultimate_sender_fake_period_ms = signal FakeMessageGenerator.calculatePeriod();
		message.ultimate_sender_fake_count = fake_count;

		if (send_Fake_message(&message, AM_BROADCAST_ADDR))
		{
			const uint32_t sent_time = call PacketTimeStamp.isValid(&packet)
				? call PacketTimeStamp.timestamp(&packet)
				: call LocalTime.get();

			sequence_number_increment(&fake_sequence_counter);

			fake_count += 1;

			process_fake_duty_cycle(&packet, &message, TRUE, sent_time);
		}
	}

	event void FakeMessageGenerator.durationExpired(const void* original, uint8_t original_size, uint32_t duration_expired_at)
	{
		ChooseMessage new_message;

		const am_addr_t target = fake_walk_target();
		const uint8_t node_type = call NodeType.get();

		bool ack_request = TRUE;

		//assert(sizeof(message) == original_size);

		memcpy(&new_message, original, sizeof(new_message));

		simdbgverbose("stdout", "Finished sending Fake from TFS, now sending Choose to " TOS_NODE_ID_SPEC ".\n", target);

		// When finished sending fake messages from a TFS
		new_message.sink_distance += 1;
		new_message.any_further = any_further_neighbours();
		new_message.ultimate_sender_first_source_distance = first_source_distance;

		// send the new node type
		new_message.source_node_type = (node_type == PermFakeNode) ? NormalNode : TailFakeNode;

		choose_rtx_limit = CHOOSE_RTX_LIMIT_FOR_FS;
		send_Choose_message(&new_message, target, &ack_request);

		if (call NodeType.get() == PermFakeNode)
		{
			become_Normal();
		}
		else if (node_type == TempFakeNode || node_type == TailFakeNode)
		{
			ChooseMessage original_message;
			memcpy(&original_message, original, sizeof(original_message));

			become_Fake(&original_message, TailFakeNode, duration_expired_at);
		}
		else
		{
			__builtin_unreachable();
		}
	}
}
