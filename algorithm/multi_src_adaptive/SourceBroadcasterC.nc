#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "AwayChooseMessage.h"
#include "FakeMessage.h"
#include "NormalMessage.h"

#include <Timer.h>
#include <TinyError.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, msg->sink_distance + 1)
#define METRIC_RCV_CHOOSE(msg) METRIC_RCV(Choose, source_addr, msg->source_id, msg->sequence_number, msg->sink_distance + 1)
#define METRIC_RCV_FAKE(msg) METRIC_RCV(Fake, source_addr, msg->source_id, msg->sequence_number, BOTTOM)

#define AWAY_DELAY_MS (SOURCE_PERIOD_MS / 2)

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

	uses interface MetricLogging;
	uses interface MetricHelpers;

	uses interface NodeType;
	uses interface MessageType;
	uses interface FakeMessageGenerator;
	uses interface ObjectDetector;

	uses interface SequenceNumbers as NormalSeqNos;

	// The distance between this node and each source
	uses interface Dictionary<am_addr_t, uint16_t> as SourceDistances;

	// The distance between the recorded source and the sink
	//uses interface Dictionary<am_addr_t, uint16_t> as SinkSourceDistances;
}

implementation
{
	enum
	{
		SourceNode, SinkNode, NormalNode, TempFakeNode, PermFakeNode
	};

	SequenceNumber away_sequence_counter;
	SequenceNumber choose_sequence_counter;
	SequenceNumber fake_sequence_counter;

	SequenceNumber source_fake_sequence_counter;
	uint32_t source_fake_sequence_increments;

	int32_t min_sink_source_distance;
	int32_t min_source_distance;
	int32_t sink_distance;

	bool sink_received_away_reponse;
	bool seen_pfs;
	bool is_pfs_candidate;

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

	uint16_t estimated_number_of_sources(void)
	{
		return max(1, call SourceDistances.count());
	}

	bool should_process_choose(void)
	{
		switch (algorithm)
		{
		case GenericAlgorithm:
			return min_sink_source_distance == BOTTOM || min_source_distance == BOTTOM ||
				min_source_distance > (4 * min_sink_source_distance) / 5;

		case FurtherAlgorithm:
			return !seen_pfs && (min_sink_source_distance == BOTTOM || min_source_distance == BOTTOM ||
				min_source_distance > ((1 * min_sink_source_distance) / 2) - 1);

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
	uint32_t get_dist_to_pull_back(void)
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
			if (min_source_distance == BOTTOM || min_sink_source_distance == BOTTOM)
			{
				distance = sink_distance;
			}
			else
			{
				distance = min_source_distance - min_sink_source_distance;
			}
			break;

		default:
		case FurtherAlgorithm:
			distance = max(min_sink_source_distance, sink_distance);
			break;
		}

		distance = max(distance, 1);
		
		return distance;	
	}

#elif defined(PB_ATTACKER_EST_APPROACH)
	uint32_t get_dist_to_pull_back(void)
	{
		int32_t distance = 0;

		switch (algorithm)
		{
		case GenericAlgorithm:
			distance = sink_distance + sink_distance;
			break;

		default:
		case FurtherAlgorithm:
			distance = max(min_sink_source_distance, sink_distance);
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
		const uint32_t distance = get_dist_to_pull_back();
		const uint32_t est_num_sources = estimated_number_of_sources();

		simdbgverbose("stdout", "get_tfs_num_msg_to_send=%u, (Dsrc=%d, Dsink=%d, Dss=%d)\n",
			distance, source_distance, sink_distance, min_sink_source_distance);

		return distance * est_num_sources;
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

		const double x = seq_inc / (double)counter;

		const uint32_t result_period = ceil(SOURCE_PERIOD_MS * x);

		simdbgverbose("stdout", "get_pfs_period=%u (sent=%u, rcvd=%u, x=%f)\n",
			result_period, counter, seq_inc, x);

		return result_period;
	}

	void update_source_distance(const NormalMessage* rcvd)
	{
		const uint16_t* distance = call SourceDistances.get(rcvd->source_id);
		//const uint16_t* sink_source_distance = call SinkSourceDistances.get(rcvd->source_id);

		if (distance == NULL)
		{
			call SourceDistances.put(rcvd->source_id, rcvd->source_distance + 1);
		}
		else
		{
			call SourceDistances.put(rcvd->source_id, min(*distance, rcvd->source_distance + 1));
		}

		if (min_source_distance == BOTTOM || min_source_distance > rcvd->source_distance + 1)
		{
			min_source_distance = rcvd->source_distance + 1;
		}
		
		/*if (rcvd->sink_distance != BOTTOM)
		{
			min_sink_source_distance = minbot(min_sink_source_distance, rcvd->sink_distance + 1);

			if (sink_source_distance == NULL)
			{
				//simdbg("stdout", "Updating sink distance of %u to %d\n", rcvd->source_id, rcvd->sink_distance);
				call SinkSourceDistances.put(rcvd->source_id, rcvd->sink_distance);
			}
			else
			{
				call SinkSourceDistances.put(rcvd->source_id, min(*sink_source_distance, rcvd->sink_distance));
			}
		}*/
	}

	bool busy;
	message_t packet;

	event void Boot.booted()
	{
		LOG_STDOUT_VERBOSE(EVENT_BOOTED, "booted\n");

		busy = FALSE;
		call Packet.clear(&packet);

		min_sink_source_distance = BOTTOM;
		min_source_distance = BOTTOM;
		sink_distance = BOTTOM;

		sink_received_away_reponse = FALSE;
		seen_pfs = FALSE;
		is_pfs_candidate = FALSE;

		first_source_distance = BOTTOM;

		away_messages_to_send = 2;

		extra_to_send = 0;

		algorithm = UnknownAlgorithm;

		sequence_number_init(&away_sequence_counter);
		sequence_number_init(&choose_sequence_counter);
		sequence_number_init(&fake_sequence_counter);

		source_fake_sequence_increments = 0;
		sequence_number_init(&source_fake_sequence_counter);

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

			first_source_distance = 0;
			min_source_distance = 0;
		}
	}

	event void ObjectDetector.stoppedDetecting()
	{
		if (call NodeType.get() == SourceNode)
		{
			call BroadcastNormalTimer.stop();

			call NodeType.set(NormalNode);

			first_source_distance = BOTTOM;
			min_source_distance = BOTTOM;
		}
	}

	USE_MESSAGE_NO_EXTRA_TO_SEND(Normal);
	USE_MESSAGE_WITH_CALLBACK(Away);
	USE_MESSAGE(Choose);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Fake);

	void become_Normal(void)
	{
		call NodeType.set(NormalNode);

		call FakeMessageGenerator.stop();
	}

	void become_Fake(const AwayChooseMessage* message, uint8_t fake_type)
	{
#ifdef SLP_VERBOSE_DEBUG
		assert(fake_type == PermFakeNode || fake_type == TempFakeNode);
#endif

		// Stop any existing fake message generation.
		call FakeMessageGenerator.stop();

		call NodeType.set(fake_type);

		switch (fake_type)
		{
		case PermFakeNode:
			call FakeMessageGenerator.start(message, sizeof(*message));
			break;

		case TempFakeNode:
			call FakeMessageGenerator.startLimited(message, sizeof(*message), get_tfs_duration());
			break;

		default:
			__builtin_unreachable();
		}
	}

	void decide_not_pfs_candidate(uint16_t max_hop)
	{
		// TODO: "max_hop != UINT16_MAX" is a hack, find out where UINT16_MAX comes from and fix it!

		if (is_pfs_candidate && first_source_distance != BOTTOM && max_hop > first_source_distance + 1 && max_hop != UINT16_MAX)
		{
			is_pfs_candidate = FALSE;
			call Leds.led1Off();
		}
	}

	uint16_t new_max_hop(uint16_t max_hop)
	{
		if (first_source_distance == BOTTOM)
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
		message.max_hop = new_max_hop((min_sink_source_distance != BOTTOM) ? min_sink_source_distance : 0);
		message.min_sink_source_distance = min_sink_source_distance;

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
		message.min_sink_source_distance = min_sink_source_distance;
		message.max_hop = new_max_hop((min_sink_source_distance != BOTTOM) ? min_sink_source_distance : 0);
		message.algorithm = ALGORITHM;

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

	void Normal_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		decide_not_pfs_candidate(rcvd->max_hop);

		update_source_distance(rcvd);

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
				is_pfs_candidate = TRUE;
				call Leds.led1On();
			}

			forwarding_message = *rcvd;
			forwarding_message.min_sink_source_distance = min_sink_source_distance;
			forwarding_message.source_distance += 1;
			forwarding_message.max_hop = new_max_hop(rcvd->max_hop);
			forwarding_message.fake_sequence_number = source_fake_sequence_counter;
			forwarding_message.fake_sequence_increments = source_fake_sequence_increments;

			send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Sink_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		update_source_distance(rcvd);

		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			if (!sink_received_away_reponse)
			{
				// Forward on the normal message to help set up
				// good distances for nodes around the source
				NormalMessage forwarding_message = *rcvd;
				forwarding_message.min_sink_source_distance = min_sink_source_distance;
				forwarding_message.source_distance += 1;
				forwarding_message.max_hop = new_max_hop(rcvd->max_hop);
				forwarding_message.fake_sequence_number = source_fake_sequence_counter;
				forwarding_message.fake_sequence_increments = source_fake_sequence_increments;

				send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);

				call AwaySenderTimer.startOneShot(AWAY_DELAY_MS);
			}
		}
	}

	void Fake_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		update_source_distance(rcvd);

		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.min_sink_source_distance = min_sink_source_distance;
			forwarding_message.source_distance += 1;
			forwarding_message.max_hop = max(first_source_distance, rcvd->max_hop);
			forwarding_message.fake_sequence_number = source_fake_sequence_counter;
			forwarding_message.fake_sequence_increments = source_fake_sequence_increments;

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

	void Sink_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		sink_received_away_reponse = TRUE;
	}

	void Source_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);
		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->sink_distance + 1);
		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.min_sink_source_distance = min_sink_source_distance;
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;

			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Normal_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		decide_not_pfs_candidate(rcvd->max_hop);

		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);
		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			if (rcvd->sink_distance == 0)
			{
				become_Fake(rcvd, TempFakeNode);

				sequence_number_increment(&choose_sequence_counter);
			}

			forwarding_message = *rcvd;
			forwarding_message.min_sink_source_distance = min_sink_source_distance;
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

		sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);
		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.min_sink_source_distance = min_sink_source_distance;
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;
			forwarding_message.max_hop = new_max_hop(rcvd->max_hop);

			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Away, Receive)
		case SourceNode: Source_receive_Away(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Away(rcvd, source_addr); break;

		case PermFakeNode:
		case TempFakeNode: Fake_receive_Away(rcvd, source_addr); break;

		case SinkNode: Sink_receive_Away(rcvd, source_addr); break;
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
		sink_received_away_reponse = TRUE;
	}

	void Normal_receive_Choose(const ChooseMessage* const rcvd, am_addr_t source_addr)
	{
		decide_not_pfs_candidate(rcvd->max_hop);

		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);
		sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);

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

	RECEIVE_MESSAGE_BEGIN(Choose, Receive)
		case NormalNode: Normal_receive_Choose(rcvd, source_addr); break;
		case SinkNode: Sink_receive_Choose(rcvd, source_addr); break;

		case SourceNode:
		case TempFakeNode:
		case PermFakeNode: break;
	RECEIVE_MESSAGE_END(Choose)



	void Sink_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		sink_received_away_reponse = TRUE;

		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			message.min_sink_source_distance = min_sink_source_distance;

			send_Fake_message(&message, AM_BROADCAST_ADDR);
		}
	}

	void Source_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

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

		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			seen_pfs |= rcvd->from_pfs;

			forwarding_message.min_sink_source_distance = min_sink_source_distance;
			forwarding_message.max_hop = new_max_hop(rcvd->max_hop);

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Fake_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		decide_not_pfs_candidate(rcvd->max_hop);

		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			seen_pfs |= rcvd->from_pfs;

			forwarding_message.min_sink_source_distance = min_sink_source_distance;
			forwarding_message.max_hop = new_max_hop(rcvd->max_hop);

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);

			if (pfs_can_become_normal() &&
				call NodeType.get() == PermFakeNode &&
				rcvd->from_pfs &&
				(
					(rcvd->sender_source_distance > min_source_distance) ||
					(rcvd->sender_source_distance == min_source_distance && sink_distance < rcvd->sink_distance) ||
					(rcvd->sender_source_distance == min_source_distance && sink_distance == rcvd->sink_distance && TOS_NODE_ID < rcvd->source_id)
				)
				)
			{
				call FakeMessageGenerator.expireDuration();
			}
		}
	}

	RECEIVE_MESSAGE_BEGIN(Fake, Receive)
		case SinkNode: Sink_receive_Fake(rcvd, source_addr); break;
		case SourceNode: Source_receive_Fake(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Fake(rcvd, source_addr); break;
		case TempFakeNode:
		case PermFakeNode: Fake_receive_Fake(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Fake)

	event uint32_t FakeMessageGenerator.initialStartDelay()
	{
		// The first fake message is to be sent half way through the period.
		// After this message is sent, all other messages are sent with an interval
		// of the period given. The aim here is to reduce the traffic at the start and
		// end of the TFS duration.
		return signal FakeMessageGenerator.calculatePeriod() / 2;
	}

	event uint32_t FakeMessageGenerator.calculatePeriod()
	{
		switch (call NodeType.get())
		{
		case PermFakeNode: return get_pfs_period();
		case TempFakeNode: return get_tfs_period();
		default:
			ERROR_OCCURRED(ERROR_CALLED_FMG_CALC_PERIOD_ON_NON_FAKE_NODE, "Called FakeMessageGenerator.calculatePeriod on non-fake node.\n");
			return 0;
		}
	}

	event void FakeMessageGenerator.sendFakeMessage()
	{
		FakeMessage message;

		message.sequence_number = sequence_number_next(&fake_sequence_counter);
		message.min_sink_source_distance = min_sink_source_distance;
		message.sender_source_distance = min_source_distance;
		message.max_hop = new_max_hop(0);
		message.sink_distance = sink_distance;
		message.from_pfs = (call NodeType.get() == PermFakeNode);
		message.source_id = TOS_NODE_ID;

		if (send_Fake_message(&message, AM_BROADCAST_ADDR))
		{
			sequence_number_increment(&fake_sequence_counter);
		}
	}

	event void FakeMessageGenerator.durationExpired(const void* original_message, uint8_t original_size)
	{
		ChooseMessage message;
		memcpy(&message, original_message, sizeof(message));

		simdbgverbose("SourceBroadcasterC", "Finished sending Fake from TFS, now sending Choose.\n");

		// When finished sending fake messages from a TFS

		message.min_sink_source_distance = min_sink_source_distance;
		message.sink_distance += 1;

		extra_to_send = 2;
		send_Choose_message(&message, AM_BROADCAST_ADDR);

		become_Normal();
	}
}
