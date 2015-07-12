#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"
#include "NeighbourDetail.h"

#include "AwayChooseMessage.h"
#include "FakeMessage.h"
#include "NormalMessage.h"
#include "BeaconMessage.h"

#include <Timer.h>
#include <TinyError.h>

#include <assert.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, msg->sink_distance + 1)
#define METRIC_RCV_CHOOSE(msg) METRIC_RCV(Choose, source_addr, msg->source_id, msg->sequence_number, msg->sink_distance + 1)
#define METRIC_RCV_FAKE(msg) METRIC_RCV(Fake, source_addr, msg->source_id, msg->sequence_number, BOTTOM)
#define METRIC_RCV_BEACON(msg) METRIC_RCV(Beacon, source_addr, BOTTOM, BOTTOM, BOTTOM)

typedef struct
{
	int16_t distance;
} distance_container_t;

void distance_update(distance_container_t* find, distance_container_t const* given)
{
	find->distance = minbot(find->distance, given->distance);
}

void distance_print(char* name, size_t i, am_addr_t address, distance_container_t const* contents)
{
	dbg_clear(name, "[%u] => addr=%u / dist=%d",
		i, address, contents->distance);
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

	uses interface AMSend as FakeSend;
	uses interface Receive as FakeReceive;

	uses interface AMSend as BeaconSend;
	uses interface Receive as BeaconReceive;

	uses interface FakeMessageGenerator;
	uses interface ObjectDetector;
}

implementation
{
	typedef enum
	{
		SourceNode, SinkNode, NormalNode, TempFakeNode, PermFakeNode
	} NodeType;

	NodeType type = NormalNode;

	const char* type_to_string()
	{
		switch (type)
		{
		case SourceNode: 			return "SourceNode";
		case SinkNode:				return "SinkNode  ";
		case NormalNode:			return "NormalNode";
		case TempFakeNode:			return "TempFakeNode";
		case PermFakeNode:			return "PermFakeNode";
		default:					return "<unknown> ";
		}
	}

	distance_neighbours_t neighbours;

	SequenceNumber normal_sequence_counter;
	SequenceNumber away_sequence_counter;
	SequenceNumber choose_sequence_counter;
	SequenceNumber fake_sequence_counter;

	SequenceNumber source_fake_sequence_counter;
	uint64_t source_fake_sequence_increments;


	const uint32_t away_delay = SOURCE_PERIOD_MS / 2;

	int32_t sink_source_distance = BOTTOM;
	int32_t source_distance = BOTTOM;
	int32_t sink_distance = BOTTOM;

	bool sink_sent_away = FALSE;
	bool seen_pfs = FALSE;

	uint32_t first_source_distance = 0;
	bool first_source_distance_set = FALSE;

	uint32_t extra_to_send = 0;

	typedef enum
	{
		UnknownAlgorithm, GenericAlgorithm, FurtherAlgorithm
	} Algorithm;

	Algorithm algorithm = UnknownAlgorithm;

	// Produces a random float between 0 and 1
	float random_float()
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

	int32_t ignore_choose_distance(int32_t distance)
	{
		// We contemplated changing this versus the original algorithm,
		// but decided against it.
		// By randomising this, the capture rates for the Sink Corner
		// are very bad.
		//return (int32_t)ceil(distance * random_float());
		return distance;
	}

	bool should_process_choose()
	{
		switch (algorithm)
		{
		case GenericAlgorithm:
			return !(sink_source_distance != BOTTOM &&
				source_distance <= ignore_choose_distance((4 * sink_source_distance) / 5));

		case FurtherAlgorithm:
			return !seen_pfs && !(sink_source_distance != BOTTOM &&
				source_distance <= ignore_choose_distance(((1 * sink_source_distance) / 2) - 1));

		default:
			return TRUE;
		}
	}

	bool pfs_can_become_normal()
	{
		switch (algorithm)
		{
		case GenericAlgorithm:
			return TRUE;

		case FurtherAlgorithm:
			return FALSE;

		default:
			return FALSE;
		}
	}

#if defined(PB_SINK_APPROACH)
	uint32_t get_dist_to_pull_back()
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
			if (source_distance == BOTTOM || sink_source_distance == BOTTOM)
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
	uint32_t get_dist_to_pull_back()
	{
		int32_t distance = 0;

		switch (algorithm)
		{
		case GenericAlgorithm:
			distance = sink_distance + sink_distance;
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

	uint32_t get_tfs_num_msg_to_send()
	{
		/*uint32_t distance = get_dist_to_pull_back();

		dbgverbose("stdout", "get_tfs_num_msg_to_send=%u, (Dsrc=%d, Dsink=%d, Dss=%d)\n",
			distance, source_distance, sink_distance, sink_source_distance);

		return distance;*/
		return 2;
	}

	uint32_t get_tfs_duration()
	{
		uint32_t duration = SOURCE_PERIOD_MS;

		if (sink_distance <= 1)
		{
			duration -= away_delay;
		}

		dbgverbose("stdout", "get_tfs_duration=%u (sink_distance=%d)\n", duration, sink_distance);

		return duration;
	}

	uint32_t get_tfs_period()
	{
		const uint32_t duration = get_tfs_duration();
		const uint32_t msg = get_tfs_num_msg_to_send();
		const uint32_t period = duration / msg;

		const uint32_t result_period = period;

		dbgverbose("stdout", "get_tfs_period=%u\n", result_period);

		return result_period;
	}

	uint32_t get_pfs_period()
	{
		// Need to add one here because it is possible for the values to both be 0
		// if no fake messages have ever been received.
		const uint32_t seq_inc = source_fake_sequence_increments + 1;
		const uint32_t counter = sequence_number_get(&source_fake_sequence_counter) + 1;

		const double x = seq_inc / (double)counter;

		const uint32_t result_period = ceil(SOURCE_PERIOD_MS * x);

		dbgverbose("stdout", "get_pfs_period=%u (sent=%u, rcvd=%u, x=%f)\n",
			result_period, counter, seq_inc, x);

		return result_period;
	}

	am_addr_t fake_walk_target()
	{
		am_addr_t chosen_address;
		uint32_t i;

		distance_neighbours_t local_neighbours;
		init_distance_neighbours(&local_neighbours);

		// If we don't know our sink distance then we cannot work
		// out which neighbour is in closer or further.
		if (source_distance != BOTTOM)
		{
			for (i = 0; i != neighbours.size; ++i)
			{
				distance_neighbour_detail_t const* const neighbour = &neighbours.data[i];

				if (neighbour->contents.distance > source_distance)
				{
					insert_distance_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
				}
			}
		}

		if (local_neighbours.size == 0)
		{
			dbgverbose("stdout", "No local neighbours to choose so broadcasting. (my-dist=%d, my-neighbours-size=%u)\n",
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

			dbgverbose("stdout", "Chosen %u at index %u (rnd=%u) out of %u neighbours (their-dist=%d my-dist=%d)\n",
				chosen_address, neighbour_index, rnd, local_neighbours.size,
				neighbour->contents.distance, landmark_distance);
		}

		return chosen_address;
	}

	bool busy = FALSE;
	message_t packet;

	event void Boot.booted()
	{
		dbgverbose("Boot", "%s: Application booted.\n", sim_time_string());

		sequence_number_init(&normal_sequence_counter);
		sequence_number_init(&away_sequence_counter);
		sequence_number_init(&choose_sequence_counter);
		sequence_number_init(&fake_sequence_counter);

		source_fake_sequence_increments = 0;
		sequence_number_init(&source_fake_sequence_counter);

		if (TOS_NODE_ID == SINK_NODE_ID)
		{
			type = SinkNode;
			dbg("Node-Change-Notification", "The node has become a Sink\n");
		}

		call RadioControl.start();
	}

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			dbgverbose("SourceBroadcasterC", "%s: RadioControl started.\n", sim_time_string());

			call ObjectDetector.start();
		}
		else
		{
			dbgerror("SourceBroadcasterC", "%s: RadioControl failed to start, retrying.\n", sim_time_string());

			call RadioControl.start();
		}
	}

	event void RadioControl.stopDone(error_t err)
	{
		dbgverbose("SourceBroadcasterC", "%s: RadioControl stopped.\n", sim_time_string());
	}

	event void ObjectDetector.detect()
	{
		// The sink node cannot become a source node
		if (type != SinkNode)
		{
			dbg_clear("Metric-SOURCE_CHANGE", "set,%u\n", TOS_NODE_ID);
			dbg("Node-Change-Notification", "The node has become a Source\n");

			type = SourceNode;

			call BroadcastNormalTimer.startOneShot(SOURCE_PERIOD_MS);
		}
	}

	event void ObjectDetector.stoppedDetecting()
	{
		if (type == SourceNode)
		{
			call BroadcastNormalTimer.stop();

			type = NormalNode;

			dbg_clear("Metric-SOURCE_CHANGE", "unset,%u\n", TOS_NODE_ID);
			dbg("Node-Change-Notification", "The node has become a Normal\n");
		}
	}

	uint32_t beacon_send_wait()
	{
		return 75U + (uint32_t)(50U * random_float());
	}

	USE_MESSAGE(Normal);
	USE_MESSAGE(Away);
	USE_MESSAGE(Choose);
	USE_MESSAGE(Fake);
	USE_MESSAGE(Beacon);

	void become_Normal()
	{
		type = NormalNode;

		call FakeMessageGenerator.stop();

		dbg("Fake-Notification", "The node has become a Normal\n");
	}

	void become_Fake(const AwayChooseMessage* message, NodeType perm_type)
	{
		if (perm_type != PermFakeNode && perm_type != TempFakeNode)
		{
			assert("The perm type is not correct");
		}

		type = perm_type;

		if (type == PermFakeNode)
		{
			dbg("Fake-Notification", "The node has become a PFS\n");

			call FakeMessageGenerator.start(message);
		}
		else
		{
			dbg("Fake-Notification", "The node has become a TFS\n");

			call FakeMessageGenerator.startLimited(message, get_tfs_duration());
		}
	}

	event void BroadcastNormalTimer.fired()
	{
		NormalMessage message;

		dbgverbose("SourceBroadcasterC", "%s: BroadcastNormalTimer fired.\n", sim_time_string());

		message.sequence_number = sequence_number_next(&normal_sequence_counter);
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;
		message.sink_source_distance = sink_source_distance;

		message.fake_sequence_number = sequence_number_get(&fake_sequence_counter);
		message.fake_sequence_increments = source_fake_sequence_increments;

		if (send_Normal_message(&message, AM_BROADCAST_ADDR))
		{
			sequence_number_increment(&normal_sequence_counter);
		}

		call BroadcastNormalTimer.startOneShot(SOURCE_PERIOD_MS);
	}

	event void AwaySenderTimer.fired()
	{
		AwayMessage message;
		message.sequence_number = sequence_number_next(&away_sequence_counter);
		message.source_id = TOS_NODE_ID;
		message.sink_distance = 0;
		message.sink_source_distance = sink_source_distance;
		message.algorithm = ALGORITHM;

		sequence_number_increment(&away_sequence_counter);

		// TODO sense repeat 3 in (Psource / 2)
		extra_to_send = 2;
		if (send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			sink_sent_away = TRUE;
		}
	}

	event void BeaconSenderTimer.fired()
	{
		BeaconMessage message;
		unsigned int i;

		dbgverbose("SourceBroadcasterC", "%s: BeaconSenderTimer fired.\n", sim_time_string());

		message.source_distance_of_sender = first_source_distance_set ? first_source_distance : BOTTOM;

		for (i = 0; i < sizeof(message.padding); ++i)
		{
			message.padding[i] = call Random.rand16() % UINT8_MAX;
		}

		call Packet.clear(&packet);

		send_Beacon_message(&message, AM_BROADCAST_ADDR);
	}




	void Normal_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			if (!first_source_distance_set)
			{
				first_source_distance = rcvd->source_distance + 1;
				first_source_distance_set = TRUE;
				call Leds.led1On();

				call BeaconSenderTimer.startOneShot(beacon_send_wait());
			}

			source_distance = minbot(source_distance, rcvd->source_distance + 1);

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = sink_source_distance;
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

		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			sink_source_distance = minbot(sink_source_distance, rcvd->source_distance + 1);

			if (!first_source_distance_set)
			{
				first_source_distance = rcvd->source_distance + 1;
				first_source_distance_set = TRUE;
				call Leds.led1On();

				call BeaconSenderTimer.startOneShot(beacon_send_wait());
			}

			if (!sink_sent_away)
			{
				call AwaySenderTimer.startOneShot(away_delay);
			}
		}
	}

	void Fake_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.source_distance += 1;
			forwarding_message.fake_sequence_number = source_fake_sequence_counter;
			forwarding_message.fake_sequence_increments = source_fake_sequence_increments;

			send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SinkNode: Sink_receive_Normal(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Normal(rcvd, source_addr); break;
		case TempFakeNode:
		case PermFakeNode: Fake_receive_Normal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)


	void Source_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			sink_source_distance = minbot(sink_source_distance, rcvd->sink_distance + 1);

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;

			// TODO: repeat 2
			extra_to_send = 1;
			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Normal_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);

			if (rcvd->sink_distance == 0)
			{
				distance_neighbour_detail_t* neighbour = find_distance_neighbour(&neighbours, source_addr);

				if (neighbour == NULL || neighbour->contents.distance < first_source_distance)
				{
					become_Fake(rcvd, TempFakeNode);

					sequence_number_increment(&choose_sequence_counter);
				}
			}

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;

			// TODO: repeat 2
			extra_to_send = 1;
			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Away, Receive)
		case SourceNode: Source_receive_Away(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Away(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Away)


	void Normal_receive_Choose(const ChooseMessage* const rcvd, am_addr_t source_addr)
	{
		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);
		sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);

		if (sequence_number_before(&choose_sequence_counter, rcvd->sequence_number) && should_process_choose())
		{
			sequence_number_update(&choose_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_CHOOSE(rcvd);

			if (fake_walk_target() == AM_BROADCAST_ADDR)
			{
				become_Fake(rcvd, PermFakeNode);
			}
			else
			{
				become_Fake(rcvd, TempFakeNode);
			}
		}
	}

	RECEIVE_MESSAGE_BEGIN(Choose, Receive)
		case NormalNode: Normal_receive_Choose(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Choose)



	void Sink_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			forwarding_message.sink_source_distance = sink_source_distance;

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Source_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

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
		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			seen_pfs |= rcvd->from_pfs;

			forwarding_message.sink_source_distance = sink_source_distance;

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Fake_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			seen_pfs |= rcvd->from_pfs;

			forwarding_message.sink_source_distance = sink_source_distance;

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);
		}

		if (pfs_can_become_normal() &&
			type == PermFakeNode &&
			rcvd->from_pfs &&
			(
				rcvd->sender_first_source_distance > first_source_distance ||
				(rcvd->sender_first_source_distance == first_source_distance && rcvd->source_id > TOS_NODE_ID)
			)
			)
		{
			call FakeMessageGenerator.expireDuration();
		}
	}

	RECEIVE_MESSAGE_BEGIN(Fake, Receive)
		case SinkNode: Sink_receive_Fake(rcvd, source_addr); break;
		case SourceNode: Source_receive_Fake(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Fake(rcvd, source_addr); break;
		case TempFakeNode:
		case PermFakeNode: Fake_receive_Fake(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Fake)


	void x_receieve_Beacon(const BeaconMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(rcvd, source_addr, source_distance_of_sender);

		METRIC_RCV_BEACON(rcvd);
	}

	RECEIVE_MESSAGE_BEGIN(Beacon, Receive)
		case SinkNode:
		case SourceNode:
		case NormalNode:
		case TempFakeNode:
		case PermFakeNode: x_receieve_Beacon(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Fake)


	event uint32_t FakeMessageGenerator.calculatePeriod()
	{
		if (type == PermFakeNode)
		{
			return get_pfs_period();
		}
		else if (type == TempFakeNode)
		{
			return get_tfs_period();
		}
		else
		{
			dbgerror("stdout", "Called FakeMessageGenerator.calculatePeriod on non-fake node.\n");
			return 0;
		}
	}

	event void FakeMessageGenerator.generateFakeMessage(FakeMessage* message)
	{
		message->sequence_number = sequence_number_next(&fake_sequence_counter);
		message->sink_source_distance = sink_source_distance;
		message->source_distance = source_distance;
		message->sink_distance = sink_distance;
		message->from_pfs = (type == PermFakeNode);
		message->source_id = TOS_NODE_ID;
		message->sender_first_source_distance = first_source_distance_set ? first_source_distance : BOTTOM;
	}

	event void FakeMessageGenerator.durationExpired(const AwayChooseMessage* original_message)
	{
		ChooseMessage message = *original_message;
		am_addr_t target = fake_walk_target();

		dbg("stdout", "Finished sending Fake from TFS, now sending Choose to %u.\n", target);

		// When finished sending fake messages from a TFS

		message.sink_source_distance = sink_source_distance;
		message.sink_distance += 1;

		// TODO: repeat 3
		extra_to_send = 3;
		send_Choose_message(&message, target);

		if (type == PermFakeNode)
		{
			become_Normal();
		}
		else
		{
			become_Fake(original_message, PermFakeNode);
		}
	}

	event void FakeMessageGenerator.sent(error_t error, const FakeMessage* tosend)
	{
		const char* result;

		// Only if the message was successfully broadcasted, should the seqno be incremented.
		if (error == SUCCESS)
		{
			sequence_number_increment(&fake_sequence_counter);
		}

		dbgverbose("SourceBroadcasterC", "Sent Fake with error=%u.\n", error);

		switch (error)
		{
		case SUCCESS: result = "success"; break;
		case EBUSY: result = "busy"; break;
		default: result = "failed"; break;
		}

		METRIC_BCAST(Fake, result, (tosend != NULL) ? tosend->sequence_number : BOTTOM);
	}
}
