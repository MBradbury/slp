#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "AwayChooseMessage.h"
#include "FakeMessage.h"
#include "NormalMessage.h"

#include <Timer.h>
#include <TinyError.h>

#include <assert.h>

#define METRIC_RCV(TYPE, DISTANCE) \
	dbg_clear("Metric-RCV", "%s,%" PRIu64 ",%u,%u,%u,%u,%u\n", #TYPE, sim_time(), TOS_NODE_ID, source_addr, rcvd->source_id, rcvd->sequence_number, DISTANCE)

#define METRIC_BCAST(TYPE, STATUS) \
	dbg_clear("Metric-BCAST", "%s,%" PRIu64 ",%u,%s,%u\n", #TYPE, sim_time(), TOS_NODE_ID, STATUS, (tosend != NULL) ? tosend->sequence_number : (uint32_t)-1)

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;
	uses interface Random;

	uses interface Timer<TMilli> as BroadcastNormalTimer;
	uses interface Timer<TMilli> as AwaySenderTimer;

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

	uses interface FakeMessageGenerator;
	uses interface ObjectDetector;
	uses interface SourcePeriodModel;
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

	SequenceNumber normal_sequence_counter;
	SequenceNumber away_sequence_counter;
	SequenceNumber choose_sequence_counter;
	SequenceNumber fake_sequence_counter;

	SequenceNumber source_fake_sequence_counter;
	uint64_t source_fake_sequence_increments;

	int32_t sink_source_distance = BOTTOM;
	int32_t source_distance = BOTTOM;
	int32_t sink_distance = BOTTOM;

	int32_t source_period = BOTTOM;

	bool sink_sent_away = FALSE;
	bool seen_pfs = FALSE;
	bool is_pfs_candidate = FALSE;

	uint32_t first_source_distance = 0;
	bool first_source_distance_set = FALSE;

	int32_t source_node_id = BOTTOM;

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

	uint32_t get_away_delay()
	{
		assert(source_period != BOTTOM);

		return source_period / 2;
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
		uint32_t distance = get_dist_to_pull_back();

		dbgverbose("stdout", "get_tfs_num_msg_to_send=%u, (Dsrc=%d, Dsink=%d, Dss=%d)\n",
			distance, source_distance, sink_distance, sink_source_distance);

		return distance;
	}

	uint32_t get_tfs_duration()
	{
		uint32_t duration = source_period;

		assert(source_period != BOTTOM);

		if (sink_distance <= 1)
		{
			duration -= get_away_delay();
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

		const uint32_t result_period = ceil(source_period * x);

		assert(source_period != BOTTOM);

		dbgverbose("stdout", "get_pfs_period=%u (sent=%u, rcvd=%u, x=%f)\n",
			result_period, counter, seq_inc, x);

		return result_period;
	}

	// This function is to be used by the source node to get the
	// period it should use at the current time.
	// DO NOT use this for nodes other than the source!
	uint32_t get_source_period()
	{
		assert(type == SourceNode);
		return call SourcePeriodModel.get();;
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

			call BroadcastNormalTimer.startOneShot(get_source_period());
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

	USE_MESSAGE(Normal);
	USE_MESSAGE(Away);
	USE_MESSAGE(Choose);
	USE_MESSAGE(Fake);

	void become_Normal()
	{
		type = NormalNode;

		call FakeMessageGenerator.stop();

		dbg("Fake-Notification", "The node has become a Normal\n");
	}

	void become_Fake(const AwayChooseMessage* message, NodeType perm_type)
	{
		assert(perm_type == PermFakeNode || perm_type == TempFakeNode);

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

		source_period = get_source_period();

		dbgverbose("SourceBroadcasterC", "%s: BroadcastNormalTimer fired.\n", sim_time_string());

		message.sequence_number = sequence_number_next(&normal_sequence_counter);
		message.source_distance = 0;
		message.max_hop = first_source_distance;
		message.source_id = TOS_NODE_ID;
		message.sink_source_distance = sink_distance;

		message.fake_sequence_number = sequence_number_get(&fake_sequence_counter);
		message.fake_sequence_increments = source_fake_sequence_increments;

		message.source_period = source_period;

		if (send_Normal_message(&message, AM_BROADCAST_ADDR))
		{
			sequence_number_increment(&normal_sequence_counter);
		}

		call BroadcastNormalTimer.startOneShot(source_period);
	}

	event void AwaySenderTimer.fired()
	{
		AwayMessage message;
		message.sequence_number = sequence_number_next(&away_sequence_counter);
		message.sink_distance = 0;
		message.sink_source_distance = sink_source_distance;
		message.max_hop = sink_source_distance;
		message.source_id = TOS_NODE_ID;
		message.algorithm = ALGORITHM;
		message.source_period = source_period;

		sequence_number_increment(&away_sequence_counter);

		// TODO sense repeat 3 in (Psource / 2)
		extra_to_send = 2;
		if (send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			sink_sent_away = TRUE;
		}
	}

	bool handle_source_id_changed(const NormalMessage* const rcvd)
	{
		// If the source has changed or this is the first time that we have received a Normal message
		if (rcvd->source_id != source_node_id)
		{
			dbg_clear("Metric-SOURCE_CHANGE_DETECT", "%" PRIu64 ",%u,%d,%u\n", sim_time(), TOS_NODE_ID, source_node_id, rcvd->source_id);

			source_node_id = rcvd->source_id;

			// Reset variables to the new values
			source_distance = rcvd->source_distance + 1;
			sink_source_distance = rcvd->sink_source_distance;

			return TRUE;
		}
		else
		{
			return FALSE;
		}
	}

	void Normal_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (!first_source_distance_set || rcvd->max_hop > first_source_distance + 1)
		{
			is_pfs_candidate = FALSE;
			call Leds.led1Off();
		}

		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Normal, rcvd->source_distance + 1);

			source_period = rcvd->source_period;

			handle_source_id_changed(rcvd);

			dbgverbose("SourceBroadcasterC", "%s: Received unseen Normal seqno=%u from %u.\n", sim_time_string(), rcvd->sequence_number, source_addr);

			if (!first_source_distance_set)
			{
				first_source_distance = rcvd->source_distance + 1;
				is_pfs_candidate = TRUE;
				first_source_distance_set = TRUE;
				call Leds.led1On();
			}

			source_distance = minbot(source_distance, rcvd->source_distance + 1);

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.source_distance += 1;
			forwarding_message.max_hop = max(first_source_distance, rcvd->max_hop);
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

			METRIC_RCV(Normal, rcvd->source_distance + 1);

			source_period = rcvd->source_period;

			handle_source_id_changed(rcvd);

			sink_source_distance = minbot(sink_source_distance, rcvd->source_distance + 1);

			if (!sink_sent_away)
			{
				call AwaySenderTimer.startOneShot(get_away_delay());
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

			METRIC_RCV(Normal, rcvd->source_distance + 1);

			source_period = rcvd->source_period;

			if (handle_source_id_changed(rcvd))
			{
				// TODO:
				// Consider changing the pater of fake sources to reflect
				// the new source location
			}

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.source_distance += 1;
			forwarding_message.max_hop = max(first_source_distance, rcvd->max_hop);
			forwarding_message.fake_sequence_number = source_fake_sequence_counter;
			forwarding_message.fake_sequence_increments = source_fake_sequence_increments;

			send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal)
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

		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Away, rcvd->sink_distance + 1);

			if (source_period == BOTTOM)
			{
				source_period = rcvd->source_period;
			}

			sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);
			sink_source_distance = minbot(sink_source_distance, sink_distance);

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
		if (!first_source_distance_set || rcvd->max_hop > first_source_distance + 1)
		{
			is_pfs_candidate = FALSE;
			call Leds.led1Off();
		}

		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Away, rcvd->sink_distance + 1);

			if (source_period == BOTTOM)
			{
				source_period = rcvd->source_period;
			}

			sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);

			if (rcvd->sink_distance == 0)
			{
				become_Fake(rcvd, TempFakeNode);

				sequence_number_increment(&choose_sequence_counter);
			}

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;
			forwarding_message.max_hop = max(first_source_distance, rcvd->max_hop);

			// TODO: repeat 2
			extra_to_send = 1;
			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Away)
		case SourceNode: Source_receive_Away(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Away(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Away)


	void Normal_receive_Choose(const ChooseMessage* const rcvd, am_addr_t source_addr)
	{
		if (!first_source_distance_set || rcvd->max_hop > first_source_distance + 1)
		{
			is_pfs_candidate = FALSE;
			call Leds.led1Off();
		}

		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);
		sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);

		if (sequence_number_before(&choose_sequence_counter, rcvd->sequence_number) && should_process_choose())
		{
			sequence_number_update(&choose_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Choose, rcvd->sink_distance + 1);

			if (source_period == BOTTOM)
			{
				source_period = rcvd->source_period;
			}

			if (is_pfs_candidate)
			{
				become_Fake(rcvd, PermFakeNode);
			}
			else
			{
				become_Fake(rcvd, TempFakeNode);
			}
		}
	}

	RECEIVE_MESSAGE_BEGIN(Choose)
		case NormalNode: Normal_receive_Choose(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Choose)



	void Sink_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Fake, 0);

			message.sink_source_distance = sink_source_distance;

			send_Fake_message(&message, AM_BROADCAST_ADDR);
		}
	}

	void Source_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);
			source_fake_sequence_increments += 1;

			METRIC_RCV(Fake, 0);

			seen_pfs |= rcvd->from_pfs;
		}
	}

	void Normal_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		if (!first_source_distance_set || rcvd->max_hop > first_source_distance + 1)
		{
			is_pfs_candidate = FALSE;
			call Leds.led1Off();
		}

		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Fake, 0);

			seen_pfs |= rcvd->from_pfs;

			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.max_hop = max(first_source_distance, forwarding_message.max_hop);

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Fake_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		if (!first_source_distance_set || rcvd->max_hop > first_source_distance + 1)
		{
			is_pfs_candidate = FALSE;
			call Leds.led1Off();
		}

		sink_source_distance = minbot(sink_source_distance, rcvd->sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Fake, 0);

			seen_pfs |= rcvd->from_pfs;

			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.max_hop = max(first_source_distance, forwarding_message.max_hop);

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);

			if (pfs_can_become_normal() &&
				type == PermFakeNode &&
				rcvd->from_pfs &&
				(
					(rcvd->source_distance > source_distance) ||
					(rcvd->source_distance == source_distance && sink_distance < rcvd->sink_distance) ||
					(rcvd->source_distance == source_distance && sink_distance == rcvd->sink_distance && TOS_NODE_ID < rcvd->source_id)
				)
				)
			{
				call FakeMessageGenerator.expireDuration();
			}
		}
	}

	RECEIVE_MESSAGE_BEGIN(Fake)
		case SinkNode: Sink_receive_Fake(rcvd, source_addr); break;
		case SourceNode: Source_receive_Fake(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Fake(rcvd, source_addr); break;
		case TempFakeNode:
		case PermFakeNode: Fake_receive_Fake(rcvd, source_addr); break;
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
		message->max_hop = first_source_distance;
		message->sink_distance = sink_distance;
		message->from_pfs = (type == PermFakeNode);
		message->source_id = TOS_NODE_ID;
	}

	event void FakeMessageGenerator.durationExpired(const AwayChooseMessage* original_message)
	{
		ChooseMessage message = *original_message;

		dbgverbose("SourceBroadcasterC", "Finished sending Fake from TFS, now sending Choose.\n");

		// When finished sending fake messages from a TFS

		message.sink_source_distance = sink_source_distance;
		message.sink_distance += 1;

		// TODO: repeat 3
		extra_to_send = 2;
		send_Choose_message(&message, AM_BROADCAST_ADDR);

		become_Normal();
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

		METRIC_BCAST(Fake, result);

		if (pfs_can_become_normal())
		{
			if (type == PermFakeNode && !is_pfs_candidate)
			{
				call FakeMessageGenerator.expireDuration();
			}
		}
	}
}
