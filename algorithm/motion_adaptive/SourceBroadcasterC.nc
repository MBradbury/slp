#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"
#include "NeighbourDetail.h"

#include "AwayChooseMessage.h"
#include "FakeMessage.h"
#include "NormalMessage.h"
#include "MoveMessage.h"

#include <Timer.h>
#include <TinyError.h>

#include <assert.h>

#define METRIC_RCV(TYPE, DISTANCE, ULTIMATE_SOURCE) \
	simdbg_clear("Metric-RCV", "%s,%" PRIu64 ",%u,%u,%u,%u,%u\n", #TYPE, sim_time(), TOS_NODE_ID, source_addr, ULTIMATE_SOURCE, rcvd->sequence_number, DISTANCE)

typedef struct
{
	int16_t sink_distance;
	int16_t source_distance;
} distance_container_t;

void dist_update(distance_container_t* find, distance_container_t const* given)
{
	memcpy(find, given, sizeof(distance_container_t));
}

void dist_print(char* name, size_t i, am_addr_t address, distance_container_t const* contents)
{
	simdbg_clear(name, "[%u] => addr=%u / dsink=%d / dsrc=%d",
		i, address, contents->sink_distance, contents->source_distance);
}

DEFINE_NEIGHBOUR_DETAIL(distance_container_t, dist, dist_update, dist_print, 16);

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;
	uses interface Random;

	uses interface Timer<TMilli> as BroadcastNormalTimer;
	uses interface Timer<TMilli> as AwaySenderTimer;

	uses interface Packet;
	uses interface AMPacket;
	uses interface PacketLink;
	uses interface PacketAcknowledgements;

	uses interface SplitControl as RadioControl;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;

	uses interface AMSend as AwaySend;
	uses interface Receive as AwayReceive;

	uses interface AMSend as ChooseSend;
	uses interface Receive as ChooseReceive;

	uses interface AMSend as FakeSend;
	uses interface Receive as FakeReceive;

	uses interface AMSend as MoveSend;
	uses interface Receive as MoveReceive;

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

	dist_neighbours_t neighbours;

	SequenceNumber normal_sequence_counter;
	SequenceNumber away_sequence_counter;
	SequenceNumber choose_sequence_counter;
	SequenceNumber fake_sequence_counter;

	SequenceNumber source_fake_sequence_counter;
	uint64_t source_fake_sequence_increments;

	double sink_source_distance_ewma;
	double source_distance_ewma;
	double sink_distance_ewma;

	bool sink_source_distance_set = FALSE;
	bool source_distance_set = FALSE;
	bool sink_distance_set = FALSE;

	int32_t source_period = BOTTOM;

	bool sink_sent_away = FALSE;
	bool seen_pfs = FALSE;

	bool is_pfs_candidate = FALSE;
	bool forced_pfs = FALSE;
	int32_t waiting_for_forced_pfs = BOTTOM;

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

	int32_t get_sink_source_distance()
	{
		return sink_source_distance_set ? (int32_t)floor(sink_source_distance_ewma + 0.5) : BOTTOM;
	}
	int32_t get_source_distance()
	{
		return source_distance_set ? (int32_t)floor(source_distance_ewma + 0.5) : BOTTOM;
	}
	int32_t get_sink_distance()
	{
		return sink_distance_set ? (int32_t)floor(sink_distance_ewma + 0.5) : BOTTOM;
	}

	bool should_process_choose()
	{
		switch (algorithm)
		{
		case GenericAlgorithm:
			return !(get_sink_source_distance() != BOTTOM &&
				get_source_distance() <= ignore_choose_distance((4 * get_sink_source_distance()) / 5));

		case FurtherAlgorithm:
			return !seen_pfs && !(get_sink_source_distance() != BOTTOM &&
				get_source_distance() <= ignore_choose_distance(((1 * get_sink_source_distance()) / 2) - 1));

		default:
			return TRUE;
		}
	}

	bool pfs_can_become_normal()
	{
		if (forced_pfs)
			return FALSE;

		if (type != PermFakeNode)
			return FALSE;

		// Now decide based on the algorithm running
		switch (algorithm)
		{
		case GenericAlgorithm:
			return TRUE;

		case FurtherAlgorithm:
			return FALSE;

		// When the algorithm hasn't been set, don't allow
		// PFSs to become normal.
		case UnknownAlgorithm:
			return FALSE;

		// Don't recognise this algorithm
		default:
			simdbgerror("stdout", "unknown algorithm %d\n", algorithm);
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
			if (get_source_distance() == BOTTOM || get_sink_source_distance() == BOTTOM)
			{
				distance = get_sink_distance();
			}
			else
			{
				distance = get_source_distance() - get_sink_source_distance();
			}
			break;

		default:
		case FurtherAlgorithm:
			distance = max(get_sink_source_distance(), get_sink_distance());
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
			distance = get_sink_distance() * 2;
			break;

		default:
		case FurtherAlgorithm:
			distance = max(get_sink_source_distance(), get_sink_distance());
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

		//("stdout", "get_tfs_num_msg_to_send=%u, (Dsrc=%f, Dsink=%f, Dss=%f)\n",
		//	distance, source_distance_ewma, sink_distance_ewma, sink_source_distance_ewma);

		return distance;
	}

	uint32_t get_tfs_duration()
	{
		uint32_t duration = source_period;

		assert(source_period != BOTTOM);

		if (get_sink_distance() <= 1)
		{
			duration -= get_away_delay();
		}

		//simdbgverbose("stdout", "get_tfs_duration=%u (sink_distance=%f)\n",
		//	duration, sink_distance_ewma);

		return duration;
	}

	uint32_t get_tfs_period()
	{
		const uint32_t duration = get_tfs_duration();
		const uint32_t msg = get_tfs_num_msg_to_send();
		const uint32_t period = duration / msg;

		const uint32_t result_period = period;

		//simdbgverbose("stdout", "get_tfs_period=%u\n", result_period);

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

		//simdbgverbose("stdout", "get_pfs_period=%u (sent=%u, rcvd=%u, x=%f)\n",
		//	result_period, counter, seq_inc, x);

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

	am_addr_t choose_pfs_on_source_move(int32_t source_distance_old, int32_t sink_source_distance_old)
	{
#if defined(PFS_MOVE_RANDOM)
		// Choose a random neighbour or the current node
		const size_t num_nodes = neighbours.size;

		const uint16_t rand_index = call Random.rand16() % (num_nodes + 1);

		return num_nodes == rand_index ? TOS_NODE_ID : neighbours.data[rand_index].address;


		// TODO: move smartly based on how the real source has moved
#elif defined(PFS_MOVE_MIRROR)

		const int32_t source_distance_current = get_source_distance();
		//const int32_t sink_source_distance_current = get_sink_source_distance();

		const int32_t source_distance_diff = source_distance_current - source_distance_old;
		//const int32_t sink_source_distance_diff = sink_source_distance_current - sink_source_distance_old;

		size_t i;

		dist_neighbours_t local_neighbours;
		init_dist_neighbours(&local_neighbours);

		simdbgverbose("stdout", "MIRROR dsrc=%d diffdsrc:%d\n", source_distance_current, source_distance_diff);//, sink_source_distance_diff);

		for (i = 0; i != neighbours.size; ++i)
		{
			const dist_neighbour_detail_t* neighbour = &neighbours.data[i];

			const int32_t neighbour_source_distance_diff = source_distance_current - neighbour->contents.source_distance;
			//const int32_t neighbour_sink_source_distance_diff = sink_source_distance_current - neighbour->contents.sink_source_distance;

			simdbgverbose("stdout", "MIRROR: neighbour %d src dist diff = %d\n", neighbour->address, neighbour_source_distance_diff);

			if (source_distance_current != BOTTOM)
			{
				// If the PFS is closer to the source,
				// do not move to a node that is even closer to the source than we are.
				if (source_distance_diff < 0 && neighbour_source_distance_diff > 0)
				{
					continue;
				}

				// If the PFS is further than the source,
				// do not move to a node further from the source than we are.
				// TODO: Controversial as this moves closer to the source.
				if (source_distance_diff > 0 && neighbour_source_distance_diff < 0)
				{
					continue;
				}
			}

			/*if (sink_source_distance_current != BOTTOM)
			{
				if (!(sink_source_distance_diff < 0 && neighbour_sink_source_distance_diff < 0))
				{
					continue;
				}
			}*/

			insert_dist_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
		}

#	ifdef SLP_VERBOSE_DEBUG
		simdbgverbose("stdout", "Potential targets to move the PFS to:\n");
		print_dist_neighbours("stdout", &local_neighbours);
#	endif

		if (local_neighbours.size == 0)
		{
			// No good neighbours to move to,

			// TODO:
			// - Stay on current node?
			// - Move to random node?

			return TOS_NODE_ID;
		}
		else
		{
			const uint16_t rand_index = call Random.rand16() % local_neighbours.size;

			return local_neighbours.data[rand_index].address;
		}

#else
		// Static PFS
		return TOS_NODE_ID;
#endif
	}


#define EWMA_FACTOR 0.7

	void ewma_update(double* ewma, bool* is_set, double new_value)
	{
		if (!*is_set)
		{
			*ewma = new_value;
		}
		else
		{
			*ewma = EWMA_FACTOR * new_value + (1.0 - EWMA_FACTOR) * *ewma;
		}
		*is_set = TRUE;
	}

	void update_sink_source_distance(int32_t provided)
	{
		//sink_source_distance = minbot(sink_source_distance, provided_sink_source_distance); // Old-style

		if (provided != BOTTOM)
		{
			ewma_update(&sink_source_distance_ewma, &sink_source_distance_set, provided);
		}
	}

	void update_sink_distance(uint32_t provided)
	{
		//sink_distance = minbot(sink_distance, provided); // Old-style

		ewma_update(&sink_distance_ewma, &sink_distance_set, provided);
	}

	void update_source_distance(uint32_t provided)
	{
		//source_distance = minbot(source_distance, provided); // Old-style

		ewma_update(&source_distance_ewma, &source_distance_set, provided);
	}


	bool busy = FALSE;
	message_t packet;

	event void Boot.booted()
	{
		simdbgverbose("Boot", "%s: Application booted.\n", sim_time_string());

		init_dist_neighbours(&neighbours);

		sequence_number_init(&normal_sequence_counter);
		sequence_number_init(&away_sequence_counter);
		sequence_number_init(&choose_sequence_counter);
		sequence_number_init(&fake_sequence_counter);

		source_fake_sequence_increments = 0;
		sequence_number_init(&source_fake_sequence_counter);

		if (TOS_NODE_ID == SINK_NODE_ID)
		{
			type = SinkNode;
			update_sink_distance(0);
			simdbg("Node-Change-Notification", "The node has become a Sink\n");
		}

		call RadioControl.start();
	}

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			simdbgverbose("SourceBroadcasterC", "%s: RadioControl started.\n", sim_time_string());

			call ObjectDetector.start();
		}
		else
		{
			simdbgerror("SourceBroadcasterC", "%s: RadioControl failed to start, retrying.\n", sim_time_string());

			call RadioControl.start();
		}
	}

	event void RadioControl.stopDone(error_t err)
	{
		simdbgverbose("SourceBroadcasterC", "%s: RadioControl stopped.\n", sim_time_string());
	}

	event void ObjectDetector.detect()
	{
		// The sink node cannot become a source node
		if (type != SinkNode)
		{
			simdbg_clear("Metric-SOURCE_CHANGE", "set,%u\n", TOS_NODE_ID);
			simdbg("Node-Change-Notification", "The node has become a Source\n");

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

			simdbg_clear("Metric-SOURCE_CHANGE", "unset,%u\n", TOS_NODE_ID);
			simdbg("Node-Change-Notification", "The node has become a Normal\n");
		}
	}

	USE_MESSAGE(Normal);
	USE_MESSAGE(Away);
	USE_MESSAGE(Choose);
	USE_MESSAGE(Fake);
	USE_MESSAGE(Move);

	void become_Normal(bool should_send_choose)
	{
		assert(type == PermFakeNode || type == TempFakeNode);

		type = NormalNode;

		// If this was a forced PFS, then it isn't any more.
		forced_pfs = FALSE;
		waiting_for_forced_pfs = BOTTOM;

		call FakeMessageGenerator.stop(should_send_choose);

		simdbg("Fake-Notification", "The node has become a Normal\n");
	}

	void become_Fake(const AwayChooseMessage* message, NodeType perm_type)
	{
		assert(perm_type == PermFakeNode || perm_type == TempFakeNode);

		type = perm_type;

		if (type == PermFakeNode)
		{
			simdbg("Fake-Notification", "The node has become a PFS\n");

			call FakeMessageGenerator.start(message);
		}
		else
		{
			simdbg("Fake-Notification", "The node has become a TFS\n");

			call FakeMessageGenerator.startLimited(message, get_tfs_duration());
		}

#ifdef SLP_VERBOSE_DEBUG
		print_dist_neighbours("stdout", &neighbours);
#endif
	}

	void become_forced_PFS()
	{
		forced_pfs = TRUE;
		become_Fake(NULL, PermFakeNode);
	}

	event void BroadcastNormalTimer.fired()
	{
		NormalMessage message;

		source_period = get_source_period();

		simdbgverbose("SourceBroadcasterC", "%s: BroadcastNormalTimer fired.\n", sim_time_string());

		message.sequence_number = sequence_number_next(&normal_sequence_counter);
		message.source_distance = 0;
		message.max_hop = first_source_distance;
		message.source_id = TOS_NODE_ID;
		message.sink_source_distance = get_sink_distance();

		message.fake_sequence_number = sequence_number_get(&fake_sequence_counter);
		message.fake_sequence_increments = source_fake_sequence_increments;

		message.source_period = source_period;

		message.source_distance_of_sender = get_source_distance();
		message.sink_distance_of_sender = get_sink_distance();

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
		message.sink_source_distance = get_sink_source_distance();
		message.max_hop = get_sink_source_distance();
		message.source_id = TOS_NODE_ID;
		message.algorithm = ALGORITHM;
		message.source_period = source_period;

		message.source_distance_of_sender = get_source_distance();
		message.sink_distance_of_sender = get_sink_distance();

		// TODO sense repeat 3 in (Psource / 2)
		extra_to_send = 2;
		if (send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			sink_sent_away = TRUE;
			sequence_number_increment(&away_sequence_counter);
		}
	}

	// Returns true if the source id has changed
	bool handle_source_id_changed(const NormalMessage* const rcvd)
	{
		// If the source has changed or this is the first time that we have received a Normal message
		if (rcvd->source_id != source_node_id)
		{
			simdbg_clear("Metric-SOURCE_CHANGE_DETECT", "%" PRIu64 ",%u,%d,%u\n", sim_time(), TOS_NODE_ID, source_node_id, rcvd->source_id);

			source_node_id = rcvd->source_id;

			// Reset variables to the new values, we do not want to update the ewma here
			// as these are new values for a new source location.
			source_distance_ewma = rcvd->source_distance + 1;
			source_distance_set = TRUE;

			sink_source_distance_ewma = rcvd->sink_source_distance;
			sink_source_distance_set = TRUE;

			return TRUE;
		}
		else
		{
			return FALSE;
		}
	}


	void Normal_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		const distance_container_t dist = { rcvd->sink_distance_of_sender, rcvd->source_distance_of_sender };
		insert_dist_neighbour(&neighbours, source_addr, &dist);

		if (!first_source_distance_set || rcvd->max_hop > first_source_distance + 1)
		{
			is_pfs_candidate = FALSE;
			call Leds.led1Off();
		}

		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Normal, rcvd->source_distance + 1, rcvd->source_id);

			source_period = rcvd->source_period;

			update_sink_source_distance(rcvd->sink_source_distance);

			handle_source_id_changed(rcvd);

			simdbgverbose("SourceBroadcasterC", "%s: Received unseen Normal seqno=%u from %u.\n", sim_time_string(), rcvd->sequence_number, source_addr);

			if (!first_source_distance_set)
			{
				first_source_distance = rcvd->source_distance + 1;
				is_pfs_candidate = TRUE;
				first_source_distance_set = TRUE;
				call Leds.led1On();
			}

			update_source_distance(rcvd->source_distance + 1);

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = get_sink_source_distance();
			forwarding_message.source_distance += 1;
			forwarding_message.max_hop = max(first_source_distance, rcvd->max_hop);
			forwarding_message.fake_sequence_number = source_fake_sequence_counter;
			forwarding_message.fake_sequence_increments = source_fake_sequence_increments;

			forwarding_message.source_distance_of_sender = get_source_distance();
			forwarding_message.sink_distance_of_sender = get_sink_distance();

			send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Sink_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		const distance_container_t dist = { rcvd->sink_distance_of_sender, rcvd->source_distance_of_sender };
		insert_dist_neighbour(&neighbours, source_addr, &dist);

		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Normal, rcvd->source_distance + 1, rcvd->source_id);

			source_period = rcvd->source_period;

			handle_source_id_changed(rcvd);

			update_source_distance(rcvd->source_distance + 1);
			update_sink_source_distance(rcvd->source_distance + 1);

			if (!sink_sent_away)
			{
				call AwaySenderTimer.startOneShot(get_away_delay());
			}
		}
	}

	void Fake_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		const distance_container_t dist = { rcvd->sink_distance_of_sender, rcvd->source_distance_of_sender };
		insert_dist_neighbour(&neighbours, source_addr, &dist);

		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			const int32_t source_distance_old = get_source_distance();
			const int32_t sink_source_distance_old = get_sink_source_distance();

			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Normal, rcvd->source_distance + 1, rcvd->source_id);

			source_period = rcvd->source_period;

			update_sink_source_distance(rcvd->sink_source_distance);

			// Do not want to move this PFS, it is has already been
			// moved but has not yet received confirmation.
			if (handle_source_id_changed(rcvd) && type == PermFakeNode && waiting_for_forced_pfs == BOTTOM)
			{
				const am_addr_t next_pfs = choose_pfs_on_source_move(source_distance_old, sink_source_distance_old);

				// Only send the message if the target is not the current node
				if (next_pfs != TOS_NODE_ID)
				{
					MoveMessage message;
					message.sequence_number = 0;

					call PacketLink.setRetries(&packet, 3);
					call PacketLink.setRetryDelay(&packet, 100);
					call PacketAcknowledgements.noAck(&packet);

					if (send_Move_message(&message, next_pfs))
					{
						simdbgverbose("stdout", "sent move message to %u\n", next_pfs);
					}

					// When we receive a fake message from this node,
					// then the current node will become normal.
					waiting_for_forced_pfs = next_pfs;
				}
			}

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = get_sink_source_distance();
			forwarding_message.source_distance += 1;
			forwarding_message.max_hop = max(first_source_distance, rcvd->max_hop);
			forwarding_message.fake_sequence_number = source_fake_sequence_counter;
			forwarding_message.fake_sequence_increments = source_fake_sequence_increments;

			forwarding_message.source_distance_of_sender = get_source_distance();
			forwarding_message.sink_distance_of_sender = get_sink_distance();

			send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SinkNode: Sink_receive_Normal(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Normal(rcvd, source_addr); break;
		case TempFakeNode:
		case PermFakeNode:
			Fake_receive_Normal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)


	void Source_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		const distance_container_t dist = { rcvd->sink_distance_of_sender, rcvd->source_distance_of_sender };
		insert_dist_neighbour(&neighbours, source_addr, &dist);

		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Away, rcvd->sink_distance + 1, rcvd->source_id);

			update_sink_distance(rcvd->sink_distance + 1);
			update_sink_source_distance(rcvd->sink_distance + 1);

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = get_sink_source_distance();
			forwarding_message.sink_distance += 1;
			forwarding_message.source_period = source_period;
			forwarding_message.algorithm = algorithm;

			forwarding_message.source_distance_of_sender = get_source_distance();
			forwarding_message.sink_distance_of_sender = get_sink_distance();

			// TODO: repeat 2
			extra_to_send = 1;
			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Normal_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		const distance_container_t dist = { rcvd->sink_distance_of_sender, rcvd->source_distance_of_sender };
		insert_dist_neighbour(&neighbours, source_addr, &dist);

		if (!first_source_distance_set || rcvd->max_hop > first_source_distance + 1)
		{
			is_pfs_candidate = FALSE;
			call Leds.led1Off();
		}

		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Away, rcvd->sink_distance + 1, rcvd->source_id);

			if (source_period == BOTTOM)
			{
				source_period = rcvd->source_period;
			}

			update_sink_source_distance(rcvd->sink_source_distance);

			update_sink_distance(rcvd->sink_distance + 1);

			if (rcvd->sink_distance == 0)
			{
				become_Fake(rcvd, TempFakeNode);

				sequence_number_increment(&choose_sequence_counter);
			}

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = get_sink_source_distance();
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;
			forwarding_message.max_hop = max(first_source_distance, rcvd->max_hop);

			forwarding_message.source_distance_of_sender = get_source_distance();
			forwarding_message.sink_distance_of_sender = get_sink_distance();

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
		const distance_container_t dist = { rcvd->sink_distance_of_sender, rcvd->source_distance_of_sender };
		insert_dist_neighbour(&neighbours, source_addr, &dist);

		if (!first_source_distance_set || rcvd->max_hop > first_source_distance + 1)
		{
			is_pfs_candidate = FALSE;
			call Leds.led1Off();
		}

		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		if (sequence_number_before(&choose_sequence_counter, rcvd->sequence_number) && should_process_choose())
		{
			sequence_number_update(&choose_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Choose, rcvd->sink_distance + 1, rcvd->source_id);

			if (source_period == BOTTOM)
			{
				source_period = rcvd->source_period;
			}

			update_sink_source_distance(rcvd->sink_source_distance);
			update_sink_distance(rcvd->sink_distance + 1);

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
	RECEIVE_MESSAGE_END(Choose)



	void Sink_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		const distance_container_t dist = { rcvd->sink_distance_of_sender, rcvd->source_distance_of_sender };
		insert_dist_neighbour(&neighbours, source_addr, &dist);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			update_sink_source_distance(rcvd->sink_source_distance);

			METRIC_RCV(Fake, 0, rcvd->source_id);

			forwarding_message.sink_source_distance = get_sink_source_distance();

			forwarding_message.source_distance_of_sender = get_source_distance();
			forwarding_message.sink_distance_of_sender = get_sink_distance();

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Source_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		const distance_container_t dist = { rcvd->sink_distance_of_sender, rcvd->source_distance_of_sender };
		insert_dist_neighbour(&neighbours, source_addr, &dist);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);
			source_fake_sequence_increments += 1;

			update_sink_source_distance(rcvd->sink_source_distance);

			METRIC_RCV(Fake, 0, rcvd->source_id);

			seen_pfs |= rcvd->from_pfs;
		}
	}

	void Normal_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		const distance_container_t dist = { rcvd->sink_distance_of_sender, rcvd->source_distance_of_sender };
		insert_dist_neighbour(&neighbours, source_addr, &dist);

		if (!first_source_distance_set || rcvd->max_hop > first_source_distance + 1)
		{
			is_pfs_candidate = FALSE;
			call Leds.led1Off();
		}

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			update_sink_source_distance(rcvd->sink_source_distance);

			METRIC_RCV(Fake, 0, rcvd->source_id);

			seen_pfs |= rcvd->from_pfs;

			forwarding_message.sink_source_distance = get_sink_source_distance();
			forwarding_message.max_hop = max(first_source_distance, forwarding_message.max_hop);

			forwarding_message.source_distance_of_sender = get_source_distance();
			forwarding_message.sink_distance_of_sender = get_sink_distance();

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Fake_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		const distance_container_t dist = { rcvd->sink_distance_of_sender, rcvd->source_distance_of_sender };
		insert_dist_neighbour(&neighbours, source_addr, &dist);

		if (!first_source_distance_set || rcvd->max_hop > first_source_distance + 1)
		{
			is_pfs_candidate = FALSE;
			call Leds.led1Off();
		}

		if (waiting_for_forced_pfs != BOTTOM && waiting_for_forced_pfs == source_addr)
		{
			// This node was waiting for a fake message from
			// the PFS this fake source was moved to.

			// Stop being a PFS and do not send a choose message
			become_Normal(FALSE);
		}

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			update_sink_source_distance(rcvd->sink_source_distance);

			METRIC_RCV(Fake, 0, rcvd->source_id);

			seen_pfs |= rcvd->from_pfs;

			forwarding_message.sink_source_distance = get_sink_source_distance();
			forwarding_message.max_hop = max(first_source_distance, forwarding_message.max_hop);

			forwarding_message.source_distance_of_sender = get_source_distance();
			forwarding_message.sink_distance_of_sender = get_sink_distance();

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);

			if (pfs_can_become_normal() &&
				rcvd->from_pfs &&
				(
					(rcvd->source_distance > get_source_distance()) ||
					(rcvd->source_distance == get_source_distance() && get_sink_distance() < rcvd->sink_distance) ||
					(rcvd->source_distance == get_source_distance() && get_sink_distance() == rcvd->sink_distance && TOS_NODE_ID < rcvd->source_id)
				)
				)
			{
				// Stop being a PFS and send a choose message
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


	void Normal_receive_Move(const MoveMessage* const rcvd, am_addr_t source_addr)
	{
		become_forced_PFS();
	}

	void Fake_receive_Move(const MoveMessage* const rcvd, am_addr_t source_addr)
	{
		// Stop being a TFS/PFS and become a forced PFS without sending a choose message
		call FakeMessageGenerator.stop(FALSE);

		become_forced_PFS();
	}

	RECEIVE_MESSAGE_BEGIN(Move, Receive)
		case SinkNode: break;
		case NormalNode: Normal_receive_Move(rcvd, source_addr); break;
		case TempFakeNode: 
		case PermFakeNode: Fake_receive_Move(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Move)


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
			simdbgerror("stdout", "Called FakeMessageGenerator.calculatePeriod on non-fake node.\n");
			assert(type == PermFakeNode || type == TempFakeNode);
			return 0;
		}
	}

	event void FakeMessageGenerator.generateFakeMessage(FakeMessage* message)
	{
		assert(message != NULL);

		message->sequence_number = sequence_number_next(&fake_sequence_counter);
		message->sink_source_distance = get_sink_source_distance();
		message->source_distance = get_source_distance();
		message->max_hop = first_source_distance;
		message->sink_distance = get_sink_distance();
		message->from_pfs = (type == PermFakeNode);
		message->source_id = TOS_NODE_ID;

		message->source_distance_of_sender = get_source_distance();
		message->sink_distance_of_sender = get_sink_distance();
	}

	event void FakeMessageGenerator.durationExpired(const AwayChooseMessage* original_message, bool original_message_set, bool should_send_choose)
	{
		if (should_send_choose)
		{
			ChooseMessage message = *original_message;

			assert(original_message_set);

			simdbgverbose("SourceBroadcasterC", "Finished sending Fake from TFS, now sending Choose.\n");

			// When finished sending fake messages from a TFS

			message.sink_source_distance = get_sink_source_distance();
			message.sink_distance += 1;

			message.source_distance_of_sender = get_source_distance();
			message.sink_distance_of_sender = get_sink_distance();

			// TODO: repeat 3
			extra_to_send = 2;
			send_Choose_message(&message, AM_BROADCAST_ADDR);
		}

		// If we have just sent a choose message, we don't want to send another.
		become_Normal(FALSE);
	}

	event void FakeMessageGenerator.sent(error_t error, const FakeMessage* tosend)
	{
		const char* result;

		// Only if the message was successfully broadcasted, should the seqno be incremented.
		if (error == SUCCESS)
		{
			sequence_number_increment(&fake_sequence_counter);
		}

		simdbgverbose("SourceBroadcasterC", "Sent Fake with error=%u.\n", error);

		switch (error)
		{
		case SUCCESS: result = "success"; break;
		case EBUSY: result = "busy"; break;
		default: result = "failed"; break;
		}

		METRIC_BCAST(Fake, result, (tosend != NULL) ? tosend->sequence_number : BOTTOM);

		if (pfs_can_become_normal())
		{
			if (!is_pfs_candidate)
			{
				call FakeMessageGenerator.expireDuration();
			}
		}
	}
}
