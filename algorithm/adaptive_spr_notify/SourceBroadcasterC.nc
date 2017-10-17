#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"
#include "NeighbourDetail.h"

#include "AwayChooseMessage.h"
#include "FakeMessage.h"
#include "NormalMessage.h"
#include "BeaconMessage.h"
#include "NotifyMessage.h"

#include <Timer.h>
#include <TinyError.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, msg->sink_distance + 1)
#define METRIC_RCV_CHOOSE(msg) METRIC_RCV(Choose, source_addr, msg->source_id, msg->sequence_number, msg->sink_distance + 1)
#define METRIC_RCV_FAKE(msg) METRIC_RCV(Fake, source_addr, msg->source_id, msg->sequence_number, BOTTOM)
#define METRIC_RCV_BEACON(msg) METRIC_RCV(Beacon, source_addr, BOTTOM, UNKNOWN_SEQNO, BOTTOM)
#define METRIC_RCV_NOTIFY(msg) METRIC_RCV(Notify, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)

#define AWAY_DELAY_MS (SOURCE_PERIOD_MS / 4)

typedef struct
{
	int16_t distance;
} distance_container_t;

void distance_update(distance_container_t* find, distance_container_t const* given)
{
	find->distance = minbot(find->distance, given->distance);
}

void distance_print(const char* name, size_t i, am_addr_t address, distance_container_t const* contents)
{
#ifdef TOSSIM
	simdbg_clear(name, "[%u] => addr=%u / dist=%d",
		i, address, contents->distance);
#endif
}

DEFINE_NEIGHBOUR_DETAIL(distance_container_t, distance, distance_update, distance_print, SLP_MAX_1_HOP_NEIGHBOURHOOD);

#define UPDATE_NEIGHBOURS(rcvd, source_addr, name) \
{ \
	const distance_container_t dist = { rcvd->name }; \
	insert_distance_neighbour(&neighbours, source_addr, &dist); \
}

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;
	uses interface Random;

	uses interface Timer<TMilli> as BroadcastNormalTimer;
	uses interface Timer<TMilli> as AwaySenderTimer;
	uses interface Timer<TMilli> as ChooseSenderTimer;
	uses interface Timer<TMilli> as BeaconSenderTimer;

	uses interface Packet;
	uses interface AMPacket;

	uses interface SplitControl as RadioControl;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;

	uses interface AMSend as AwaySend;
	uses interface Receive as AwayReceive;

	uses interface AMSend as ChooseSend;
	uses interface Receive as ChooseReceive;
	uses interface Receive as ChooseSnoop;

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

#ifdef LOW_POWER_LISTENING
	uses interface LowPowerListening;
#endif
}

implementation
{
	enum
	{
		SourceNode, SinkNode, NormalNode, TempFakeNode, TailFakeNode, PermFakeNode
	};

	distance_neighbours_t neighbours;

	SequenceNumber away_sequence_counter;
	SequenceNumber choose_sequence_counter;
	SequenceNumber fake_sequence_counter;
	SequenceNumber notify_sequence_counter;

	SequenceNumber source_fake_sequence_counter;
	uint32_t source_fake_sequence_increments;

	int32_t sink_distance;

	bool sink_received_choose_reponse;

	int32_t first_source_distance;

	unsigned int away_messages_to_send;

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

	bool pfs_can_become_normal(void)
	{
		switch (algorithm)
		{
		case GenericAlgorithm:	return TRUE;
		case FurtherAlgorithm:	return FALSE;
		default:				return FALSE;
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
#	error "Technique not specified"
#endif
	}

	uint32_t get_tfs_num_msg_to_send(void)
	{
		const uint32_t distance = get_dist_to_pull_back();

		//simdbgverbose("stdout", "get_tfs_num_msg_to_send=%u, (Dsrc=%d, Dsink=%d, Dss=%d)\n",
		//	distance, source_distance, sink_distance, sink_source_distance);

		return distance;
	}

	uint32_t get_tfs_duration(void)
	{
		uint32_t duration = SOURCE_PERIOD_MS;

		if (sink_distance == BOTTOM || sink_distance <= 1)
		{
			duration -= AWAY_DELAY_MS;
		}

		simdbgverbose("stdout", "get_tfs_duration=%u (sink_distance=%d)\n", duration, sink_distance);

		return duration;
	}

	uint32_t get_tfs_period(void)
	{
		const uint32_t duration = get_tfs_duration();
		const uint32_t msg = get_tfs_num_msg_to_send();
		const uint32_t period = duration / msg;

		const uint32_t result_period = period;

		simdbgverbose("stdout", "get_tfs_period=%u\n", result_period);

		return result_period;
	}

	uint32_t get_pfs_period(void)
	{
		// Need to add one here because it is possible for the values to both be 0
		// if no fake messages have ever been received.
		const uint32_t seq_inc = source_fake_sequence_increments + 1;
		const uint32_t counter = sequence_number_get(&source_fake_sequence_counter) + 1;

		const double ratio = seq_inc / (double)counter;

		const uint32_t result_period = ceil(SOURCE_PERIOD_MS * ratio);

		simdbgverbose("stdout", "get_pfs_period=%u (sent=%u, rcvd=%u, x=%f)\n",
			result_period, counter, seq_inc, ratio);

		return result_period;
	}

	am_addr_t fake_walk_target(void)
	{
		am_addr_t chosen_address;
		uint32_t i;

		distance_neighbours_t local_neighbours;
		init_distance_neighbours(&local_neighbours);

		if (first_source_distance != BOTTOM)
		{
			for (i = 0; i != neighbours.size; ++i)
			{
				distance_neighbour_detail_t const* const neighbour = &neighbours.data[i];

				if (neighbour->contents.distance >= first_source_distance)
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
		LOG_STDOUT_VERBOSE(EVENT_BOOTED, "booted\n");

		busy = FALSE;
		call Packet.clear(&packet);

		sink_distance = BOTTOM;

		sink_received_choose_reponse = FALSE;

		first_source_distance = BOTTOM;

		away_messages_to_send = 3;

		extra_to_send = 0;

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

			// Sink always listens
#ifdef LOW_POWER_LISTENING
			call LowPowerListening.setLocalWakeupInterval(0);
#endif

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
	USE_MESSAGE(Choose);
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

				if (send_Notify_message(&message, AM_BROADCAST_ADDR))
				{
					sequence_number_increment(&notify_sequence_counter);
				}
			}
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
		return 75U + (uint32_t)(50U * random_float());
	}

	void become_Normal(void)
	{
		call NodeType.set(NormalNode);

		call FakeMessageGenerator.stop();
	}

	void become_Fake(const AwayChooseMessage* message, uint8_t fake_type)
	{
#ifdef SLP_VERBOSE_DEBUG
		assert(fake_type == PermFakeNode || fake_type == TempFakeNode || fake_type == TailFakeNode);
#endif

		// Stop any existing fake message generation.
		// This is necessary when transitioning from TempFS to TailFS.
		call FakeMessageGenerator.stop();

		call NodeType.set(fake_type);

		switch (fake_type)
		{
		case PermFakeNode:
			call FakeMessageGenerator.start(message, sizeof(*message));
			break;

		case TailFakeNode:
			call FakeMessageGenerator.startRepeated(message, sizeof(*message), get_tfs_duration());
			break;

		case TempFakeNode:
			call FakeMessageGenerator.startLimited(message, sizeof(*message), get_tfs_duration());
			break;

		default:
			__builtin_unreachable();
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

	event void ChooseSenderTimer.fired()
	{
		ChooseMessage message;
		message.sequence_number = sequence_number_next(&choose_sequence_counter);
		message.source_id = TOS_NODE_ID;
		message.sink_distance = 0;
		
#ifdef SPACE_BEHIND_SINK
		message.algorithm = GenericAlgorithm;
#else
		message.algorithm = FurtherAlgorithm;
#endif

		extra_to_send = 2;
		if (send_Choose_message(&message, AM_BROADCAST_ADDR))
		{
			sequence_number_increment(&choose_sequence_counter);
		}
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

		call Packet.clear(&packet);

		result = send_Beacon_message(&message, AM_BROADCAST_ADDR);
		if (!result)
		{
			simdbgverbose("stdout", "Send failed rescheduling beacon\n");
			call BeaconSenderTimer.startOneShot(beacon_send_wait());
		}
	}




	void Normal_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			if (first_source_distance == BOTTOM)
			{
				first_source_distance = rcvd->source_distance + 1;
				call Leds.led1On();

				call BeaconSenderTimer.startOneShot(beacon_send_wait());
			}

			forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;
			forwarding_message.fake_sequence_number = source_fake_sequence_counter;
			forwarding_message.fake_sequence_increments = source_fake_sequence_increments;

			send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Sink_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			if (first_source_distance == BOTTOM)
			{
				first_source_distance = rcvd->source_distance + 1;
				call Leds.led1On();

				call BeaconSenderTimer.startOneShot(beacon_send_wait());

				// Having the sink forward the normal message helps set up
				// the source distance gradients.
				// However, we don't want to keep doing this as it benefits the attacker.
				{
					NormalMessage forwarding_message = *rcvd;
					forwarding_message.source_distance += 1;
					forwarding_message.fake_sequence_number = source_fake_sequence_counter;
					forwarding_message.fake_sequence_increments = source_fake_sequence_increments;

					send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
				}
			}

			// Keep sending away messages until we get a valid response
			if (!sink_received_choose_reponse)
			{
				if (!call ChooseSenderTimer.isRunning())
				{
					call ChooseSenderTimer.startOneShot(AWAY_DELAY_MS);
				}
			}			
		}
	}

	void Fake_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;
			forwarding_message.fake_sequence_number = source_fake_sequence_counter;
			forwarding_message.fake_sequence_increments = source_fake_sequence_increments;

			send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SourceNode: break;
		case SinkNode: Sink_receive_Normal(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Normal(rcvd, source_addr); break;
		case TempFakeNode:
		case TailFakeNode:
		case PermFakeNode: Fake_receive_Normal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)


	void Source_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

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

	void Normal_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);

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

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);

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


	void Sink_receive_Choose(const ChooseMessage* const rcvd, am_addr_t source_addr)
	{
		sink_received_choose_reponse = TRUE;
	}

	void Normal_receive_Choose(const ChooseMessage* const rcvd, am_addr_t source_addr)
	{
		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);

		if (sequence_number_before(&choose_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&choose_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_CHOOSE(rcvd);

			if (rcvd->sink_distance == 0)
			{
				distance_neighbour_detail_t* neighbour = find_distance_neighbour(&neighbours, source_addr);

				if (neighbour == NULL || neighbour->contents.distance == BOTTOM ||
					first_source_distance == BOTTOM || neighbour->contents.distance <= first_source_distance)
				{
					become_Fake(rcvd, TempFakeNode);
				}
			}
			else
			{
				const am_addr_t target = fake_walk_target();

				if (target == AM_BROADCAST_ADDR)
				{
					become_Fake(rcvd, PermFakeNode);
				}
				else
				{
					become_Fake(rcvd, TempFakeNode);
				}
			}
		}
	}

	RECEIVE_MESSAGE_BEGIN(Choose, Receive)
		case SinkNode: Sink_receive_Choose(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Choose(rcvd, source_addr); break;

		case SourceNode:
		case PermFakeNode:
		case TempFakeNode:
		case TailFakeNode: break;
	RECEIVE_MESSAGE_END(Choose)


	void Sink_snoop_Choose(const ChooseMessage* const rcvd, am_addr_t source_addr)
	{
		sink_received_choose_reponse = TRUE;
	}

	void x_snoop_Choose(const ChooseMessage* const rcvd, am_addr_t source_addr)
	{
		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);
	}

	RECEIVE_MESSAGE_BEGIN(Choose, Snoop)
		case SinkNode: Sink_snoop_Choose(rcvd, source_addr); break;

		case SourceNode:
		case NormalNode:
		case PermFakeNode:
		case TempFakeNode:
		case TailFakeNode: x_snoop_Choose(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Choose)


	void Sink_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		sink_received_choose_reponse = TRUE;

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Source_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);
			source_fake_sequence_increments += 1;

			METRIC_RCV_FAKE(rcvd);
		}
	}

	void Normal_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Fake_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		const uint8_t type = call NodeType.get();

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);
		}

		if ((
				(rcvd->message_type == PermFakeNode && type == PermFakeNode && pfs_can_become_normal()) ||
				(rcvd->message_type == TailFakeNode && type == PermFakeNode && pfs_can_become_normal()) ||
				(rcvd->message_type == PermFakeNode && type == TailFakeNode) ||
				(rcvd->message_type == TailFakeNode && type == TailFakeNode)
			) &&
			(
				rcvd->sender_first_source_distance > first_source_distance ||
				(rcvd->sender_first_source_distance == first_source_distance && rcvd->source_id > TOS_NODE_ID)
			)
			)
		{
			// Stop fake & choose sending and become a normal node
			become_Normal();
		}
	}

	RECEIVE_MESSAGE_BEGIN(Fake, Receive)
		case SinkNode: Sink_receive_Fake(rcvd, source_addr); break;
		case SourceNode: Source_receive_Fake(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Fake(rcvd, source_addr); break;
		case TempFakeNode:
		case TailFakeNode:
		case PermFakeNode: Fake_receive_Fake(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Fake)


	void x_receive_Beacon(const BeaconMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(rcvd, source_addr, source_distance_of_sender);

		METRIC_RCV_BEACON(rcvd);
	}

	RECEIVE_MESSAGE_BEGIN(Beacon, Receive)
		case SinkNode:
		case SourceNode:
		case NormalNode:
		case TempFakeNode:
		case TailFakeNode:
		case PermFakeNode: x_receive_Beacon(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Beacon)


	void x_receive_Notify(const NotifyMessage* const rcvd, am_addr_t source_addr)
	{
		if (sequence_number_before(&notify_sequence_counter, rcvd->sequence_number))
		{
			NotifyMessage forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;

			sequence_number_update(&notify_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_NOTIFY(rcvd);

			send_Notify_message(&forwarding_message, AM_BROADCAST_ADDR);

			if (first_source_distance == BOTTOM)
			{
				first_source_distance = rcvd->source_distance + 1;
				call Leds.led1On();

				call BeaconSenderTimer.startOneShot(beacon_send_wait());
			}
		}
	}

	void Sink_receive_Notify(const NotifyMessage* const rcvd, am_addr_t source_addr)
	{
		x_receive_Notify(rcvd, source_addr);

		// Keep sending away messages until we get a valid response
		if (!sink_received_choose_reponse)
		{
			if (!call ChooseSenderTimer.isRunning())
			{
				call ChooseSenderTimer.startOneShot(AWAY_DELAY_MS);
			}
		}
	}

	RECEIVE_MESSAGE_BEGIN(Notify, Receive)
		case SinkNode: Sink_receive_Notify(rcvd, source_addr); break;

		case SourceNode:
		case NormalNode:
		case TempFakeNode:
		case TailFakeNode:
		case PermFakeNode: x_receive_Notify(rcvd, source_addr); break;
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
		message.sender_first_source_distance = first_source_distance;

		if (send_Fake_message(&message, AM_BROADCAST_ADDR))
		{
			sequence_number_increment(&fake_sequence_counter);
		}
	}

	event void FakeMessageGenerator.durationExpired(const void* original, uint8_t original_size)
	{
		ChooseMessage message;
		const am_addr_t target = fake_walk_target();

		memcpy(&message, original, sizeof(message));

		simdbgverbose("stdout", "Finished sending Fake from TFS, now sending Choose to %u.\n", target);

		// When finished sending fake messages from a TFS

		message.sink_distance += 1;

		extra_to_send = 2;
		send_Choose_message(&message, target);

		if (call NodeType.get() == PermFakeNode)
		{
			become_Normal();
		}
		else if (call NodeType.get() == TempFakeNode)
		{
			become_Fake(&message, TailFakeNode);
		}
		else //if (call NodeType.get() == TailFakeNode)
		{
		}
	}
}
