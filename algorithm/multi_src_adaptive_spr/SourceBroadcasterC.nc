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

// Notes:
/*
 * Important to remember that the algorithm cannot rely on the first flood to get the minimum distance,
 * this is because nodes will now flood at exactly the same time.
 * So we will need to maintain and update neighbours of a change in our source distances
 */

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, msg->sink_distance + 1)
#define METRIC_RCV_CHOOSE(msg) METRIC_RCV(Choose, source_addr, msg->source_id, msg->sequence_number, msg->sink_distance + 1)
#define METRIC_RCV_FAKE(msg) METRIC_RCV(Fake, source_addr, msg->source_id, msg->sequence_number, BOTTOM)
#define METRIC_RCV_BEACON(msg) METRIC_RCV(Beacon, source_addr, BOTTOM, BOTTOM, BOTTOM)

// Basically a flat map between node ids to distances
typedef struct
{
	uint16_t node[SLP_MAX_NUM_SOURCES];
	int16_t src_distance[SLP_MAX_NUM_SOURCES];
	uint16_t count;

	int16_t sink_distance;

} distance_container_t;

void distance_update(distance_container_t* __restrict find, distance_container_t const* __restrict given)
{
	uint16_t i, j;

	for (i = 0; i != given->count; ++i)
	{
		// Attempt to update existing distances
		for (j = 0; j != find->count; ++j)
		{
			if (given->node[i] == find->node[j])
			{
				find->src_distance[j] = minbot(find->src_distance[j], given->src_distance[i]);
				find->sink_distance = given->sink_distance;
				break;
			}
		}

		// Couldn't find distance, so add it
		if (j == find->count)
		{
			find->src_distance[find->count] = given->src_distance[i];
			find->count++;
		}
	}
}

void distance_print(const char* name, size_t n, am_addr_t address, distance_container_t const* contents)
{
	uint16_t i;

	dbg_clear(name, "[%u] => addr=%u {", n, address);

	for (i = 0; i != contents->count; ++i)
	{
		dbg_clear(name, "%u: %d", contents->node[i], contents->src_distance[i]);

		if (i + 1 != contents->count)
		{
			dbg_clear(name, ", ");
		}
	}

	dbg_clear(name, "}");
}

DEFINE_NEIGHBOUR_DETAIL(distance_container_t, distance, distance_update, distance_print, SLP_MAX_1_HOP_NEIGHBOURHOOD);

#define UPDATE_NEIGHBOURS(rcvd, source_addr, name) \
{ \
	distance_container_t dist; \
	dist.count = 1; \
	dist.node[0] = rcvd->source_id; \
	dist.src_distance[0] = rcvd->name; \
	dist.sink_distance = sink_distance; \
	insert_distance_neighbour(&neighbours, source_addr, &dist); \
}

#define UPDATE_NEIGHBOURS_BEACON(rcvd, source_addr) \
{ \
	uint16_t i; \
	distance_container_t dist; \
	dist.count = rcvd->count; \
	for (i = 0; i != rcvd->count; ++i) \
	{ \
		dist.node[i] = rcvd->node[i]; \
		dist.src_distance[i] = rcvd->src_distance[i]; \
	} \
	dist.sink_distance = rcvd->sink_distance; \
	insert_distance_neighbour(&neighbours, source_addr, &dist); \
}

static int16_t min_neighbour_src_distance(distance_neighbour_detail_t const* neighbour)
{
	const distance_container_t* dist = &neighbour->contents;
	uint16_t i;
	int16_t result = INT16_MAX;

	for (i = 0; i != dist->count; ++i)
	{
		result = min(result, dist->src_distance[i]);
	}

	return result;
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

	uses interface SequenceNumbers as NormalSeqNos;

	uses interface Dictionary<am_addr_t, int32_t> as SourceDistances;
}

implementation
{
	typedef enum
	{
		SourceNode, SinkNode, NormalNode, TempFakeNode, TailFakeNode, PermFakeNode
	} NodeType;

	NodeType type = NormalNode;

	const char* type_to_string()
	{
		switch (type)
		{
		case SourceNode: 			return "SourceNode";
		case SinkNode:				return "SinkNode";
		case NormalNode:			return "NormalNode";
		case TempFakeNode:			return "TempFakeNode";
		case TailFakeNode:			return "TailFakeNode";
		case PermFakeNode:			return "PermFakeNode";
		default:					return "<unknown>";
		}
	}

	distance_neighbours_t neighbours;

	SequenceNumber away_sequence_counter;
	SequenceNumber choose_sequence_counter;
	SequenceNumber fake_sequence_counter;

	SequenceNumber source_fake_sequence_counter;
	uint64_t source_fake_sequence_increments;

	int16_t min_sink_source_distance = BOTTOM;
	int16_t min_source_distance = BOTTOM;
	int16_t sink_distance = BOTTOM;

	bool sink_received_away_reponse = FALSE;

	bool first_normal_rcvd = FALSE;

	bool dw_towards_source = FALSE;

	uint32_t extra_to_send = 0;

	typedef enum
	{
		UnknownAlgorithm, GenericAlgorithm, FurtherAlgorithm
	} Algorithm;

	Algorithm algorithm = UnknownAlgorithm;

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

	uint32_t get_away_delay(void)
	{
		assert(SOURCE_PERIOD_MS != BOTTOM);

		return SOURCE_PERIOD_MS / 2;
	}

	uint32_t estimated_number_of_sources(void)
	{
		return max(1, call SourceDistances.count());
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

		//dbgverbose("stdout", "get_tfs_num_msg_to_send=%u, (Dsrc=%d, Dsink=%d, Dss=%d)\n",
		//	distance, source_distance, sink_distance, min_sink_source_distance);

		return distance;
	}

	uint32_t get_tfs_duration(void)
	{
		uint32_t duration = SOURCE_PERIOD_MS;

		if (sink_distance == BOTTOM || sink_distance <= 1)
		{
			duration -= get_away_delay();
		}

		dbgverbose("stdout", "get_tfs_duration=%u (sink_distance=%d)\n", duration, sink_distance);

		return duration;
	}

	uint32_t get_tfs_period(void)
	{
		const uint32_t duration = get_tfs_duration();
		const uint32_t msg = get_tfs_num_msg_to_send();
		const uint32_t period = duration / msg;
		const uint32_t est_num_sources = estimated_number_of_sources();

		const uint32_t result_period = (uint32_t)ceil(period / (double)est_num_sources);

		dbgverbose("stdout", "get_tfs_period=%u\n", result_period);

		return result_period;
	}

	uint32_t get_pfs_period(void)
	{
		// Need to add one here because it is possible for the values to both be 0
		// if no fake messages have ever been received.
		const uint32_t seq_inc = source_fake_sequence_increments + 1;
		const uint32_t counter = sequence_number_get(&source_fake_sequence_counter) + 1;

		const double ratio = seq_inc / (double)counter;

		const uint32_t est_num_sources = estimated_number_of_sources();

		const uint32_t result_period = (uint32_t)ceil((SOURCE_PERIOD_MS * ratio) / est_num_sources);

		dbgverbose("stdout", "get_pfs_period=%u (sent=%u, rcvd=%u, x=%f)\n",
			result_period, counter, seq_inc, ratio);

		return result_period;
	}

	void find_neighbours_further_from_source(distance_neighbours_t* local_neighbours)
	{
		size_t i;

		init_distance_neighbours(local_neighbours);

		if (min_source_distance != BOTTOM)
		{
			for (i = 0; i != neighbours.size; ++i)
			{
				distance_neighbour_detail_t const* const neighbour = &neighbours.data[i];

				if (min_neighbour_src_distance(neighbour) >= min_source_distance)
				{
					insert_distance_neighbour(local_neighbours, neighbour->address, &neighbour->contents);
				}
			}
		}
	}

	int16_t find_neighbours_with_max_sink_distance(distance_neighbours_t* local_neighbours)
	{
		size_t i;
		int16_t max_sink_distance = INT16_MIN;

		init_distance_neighbours(local_neighbours);

		// Choose the neighbour with the highest sink_distance
		for (i = 0; i != neighbours.size; ++i)
		{
			distance_neighbour_detail_t const* const neighbour = &neighbours.data[i];

			max_sink_distance = max(max_sink_distance, neighbour->contents.sink_distance);
		}

		for (i = 0; i != neighbours.size; ++i)
		{
			distance_neighbour_detail_t const* const neighbour = &neighbours.data[i];

			if (max_sink_distance == neighbour->contents.sink_distance)
			{
				insert_distance_neighbour(local_neighbours, neighbour->address, &neighbour->contents);
			}
		}

		return max_sink_distance;
	}

	typedef struct {
		am_addr_t target;
		bool towards_source;
	} fake_walk_result_t;

	// TODO: modify this to allow the directed random walk to go closer to the source
	// + (min_sink_source_distance / 2)
	// Will also need to modify TailFS reverting to Normal, as it will need to be able
	// to detect that the TFS that is closer to the source is part of the walk and a valid option
	fake_walk_result_t fake_walk_target(void)
	{
		fake_walk_result_t result = { AM_BROADCAST_ADDR, FALSE };
		//am_addr_t chosen_address = AM_BROADCAST_ADDR;
		//bool towards_source = FALSE;

		distance_neighbours_t local_neighbours;

		find_neighbours_further_from_source(&local_neighbours);

		if (local_neighbours.size == 0 && min_source_distance == BOTTOM)
		{
			dbgverbose("stdout", "No local neighbours to choose so broadcasting. (my-neighbours-size=%u)\n",
				neighbours.size); 
		}
		else if (local_neighbours.size == 0 && neighbours.size != 0)
		{
			// There are neighbours who exist that are closer to the source than this node.
			// We should consider moving to one of these neighbours if we are still close to the sink.

			if (sink_distance <= (min_sink_source_distance / 2))
			{
				find_neighbours_with_max_sink_distance(&local_neighbours);

				result.towards_source = local_neighbours.size != 0;
			}
		}
		
		if (local_neighbours.size != 0)
		{
			// Choose a neighbour with equal probabilities.
			const uint16_t rnd = call Random.rand16();
			const uint16_t neighbour_index = rnd % local_neighbours.size;
			const distance_neighbour_detail_t* const neighbour = &local_neighbours.data[neighbour_index];

			result.target = neighbour->address;

#ifdef SLP_VERBOSE_DEBUG
			print_distance_neighbours("stdout", &local_neighbours);
#endif

			dbgverbose("stdout", "Chosen %u at index %u (rnd=%u) out of %u neighbours\n",
				result.target, neighbour_index, rnd, local_neighbours.size);
		}

		return result;
	}

	void update_source_distance(const NormalMessage* rcvd)
	{
		const int32_t* distance = call SourceDistances.get(rcvd->source_id);
		if (distance == NULL || *distance > rcvd->source_distance)
		{
			call SourceDistances.put(rcvd->source_id, rcvd->source_distance);
			min_source_distance = minbot(min_source_distance, rcvd->source_distance);
		}
	}


	bool busy = FALSE;
	message_t packet;

	event void Boot.booted()
	{
		dbgverbose("Boot", "%s: Application booted.\n", sim_time_string());

		sequence_number_init(&away_sequence_counter);
		sequence_number_init(&choose_sequence_counter);
		sequence_number_init(&fake_sequence_counter);

		source_fake_sequence_increments = 0;
		sequence_number_init(&source_fake_sequence_counter);

		if (TOS_NODE_ID == SINK_NODE_ID)
		{
			type = SinkNode;
			sink_distance = 0;
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
			call SourceDistances.put(TOS_NODE_ID, 0);

			call BroadcastNormalTimer.startOneShot(SOURCE_PERIOD_MS);
		}
	}

	event void ObjectDetector.stoppedDetecting()
	{
		if (type == SourceNode)
		{
			call BroadcastNormalTimer.stop();

			type = NormalNode;
			call SourceDistances.remove(TOS_NODE_ID);

			dbg_clear("Metric-SOURCE_CHANGE", "unset,%u\n", TOS_NODE_ID);
			dbg("Node-Change-Notification", "The node has become a Normal\n");
		}
	}

	uint32_t beacon_send_wait(void)
	{
		return 75U + (uint32_t)(50U * random_float());
	}

	USE_MESSAGE(Normal);
	USE_MESSAGE(Away);
	USE_MESSAGE(Choose);
	USE_MESSAGE(Fake);
	USE_MESSAGE(Beacon);

	void become_Normal(void)
	{
		const char* const old_type = type_to_string();

		type = NormalNode;

		dw_towards_source = FALSE;
		if (dw_towards_source) { call Leds.led0On(); } else { call Leds.led0Off(); }

		call FakeMessageGenerator.stop();

		dbg("Fake-Notification", "The node has become a %s was %s\n", type_to_string(), old_type);
	}

	void become_Fake(const AwayChooseMessage* message, NodeType fake_type)
	{
		const char* const old_type = type_to_string();

		if (fake_type != PermFakeNode && fake_type != TempFakeNode && fake_type != TailFakeNode)
		{
			assert("The perm type is not correct");
		}

		// Stop any existing fake message generation.
		// This is necessary when transitioning from TempFS to TailFS.
		call FakeMessageGenerator.stop();

		type = fake_type;

		dbg("Fake-Notification", "The node has become a %s was %s\n", type_to_string(), old_type);

		if (type == PermFakeNode)
		{
			call FakeMessageGenerator.start(message);
		}
		else if (type == TailFakeNode)
		{
			call FakeMessageGenerator.startRepeated(message, get_tfs_duration());
		}
		else if (type == TempFakeNode)
		{
			call FakeMessageGenerator.startLimited(message, get_tfs_duration());
		}
		else
		{
			assert(FALSE);
		}
	}

	event void BroadcastNormalTimer.fired()
	{
		NormalMessage message;

		dbgverbose("SourceBroadcasterC", "%s: BroadcastNormalTimer fired.\n", sim_time_string());

		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;
		message.min_sink_source_distance = min_sink_source_distance;

		message.fake_sequence_number = sequence_number_get(&fake_sequence_counter);
		message.fake_sequence_increments = source_fake_sequence_increments;

		if (send_Normal_message(&message, AM_BROADCAST_ADDR))
		{
			call NormalSeqNos.increment(TOS_NODE_ID);
		}

		call BroadcastNormalTimer.startOneShot(SOURCE_PERIOD_MS);
	}

	event void AwaySenderTimer.fired()
	{
		AwayMessage message;
		message.sequence_number = sequence_number_next(&away_sequence_counter);
		message.source_id = TOS_NODE_ID;
		message.sink_distance = 0;
		message.min_sink_source_distance = min_sink_source_distance;
		message.algorithm = ALGORITHM;

		sequence_number_increment(&away_sequence_counter);

		extra_to_send = 2;
		send_Away_message(&message, AM_BROADCAST_ADDR);
	}

	event void BeaconSenderTimer.fired()
	{
		BeaconMessage message;
		uint16_t* iter;
		uint16_t i;

		dbgverbose("SourceBroadcasterC", "%s: BeaconSenderTimer fired.\n", sim_time_string());

		// Send all known source distances in the beacon message

		message.count = call SourceDistances.count();

		for (iter = call SourceDistances.beginKeys(), i = 0; iter != call SourceDistances.endKeys(); ++iter, ++i)
		{
			message.node[i] = *iter;
			message.src_distance[i] = *call SourceDistances.get_from_iter(iter);
		}

		call Packet.clear(&packet);

		send_Beacon_message(&message, AM_BROADCAST_ADDR);
	}


	void Normal_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(rcvd, source_addr, source_distance);

		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			update_source_distance(rcvd);

			if (!first_normal_rcvd)
			{
				first_normal_rcvd = TRUE;
				call Leds.led1On();

				call BeaconSenderTimer.startOneShot(beacon_send_wait());
			}

			forwarding_message = *rcvd;
			forwarding_message.min_sink_source_distance = min_sink_source_distance;
			forwarding_message.source_distance += 1;
			forwarding_message.fake_sequence_number = source_fake_sequence_counter;
			forwarding_message.fake_sequence_increments = source_fake_sequence_increments;

			send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Sink_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(rcvd, source_addr, source_distance);

		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			update_source_distance(rcvd);

			min_sink_source_distance = minbot(min_sink_source_distance, rcvd->source_distance + 1);

			if (!first_normal_rcvd)
			{
				first_normal_rcvd = TRUE;
				call Leds.led1On();

				call BeaconSenderTimer.startOneShot(beacon_send_wait());

				// Having the sink forward the normal message helps set up
				// the source distance gradients.
				// However, we don't want to keep doing this as it benefits the attacker.
				{
					NormalMessage forwarding_message = *rcvd;
					forwarding_message.min_sink_source_distance = min_sink_source_distance;
					forwarding_message.source_distance += 1;
					forwarding_message.fake_sequence_number = source_fake_sequence_counter;
					forwarding_message.fake_sequence_increments = source_fake_sequence_increments;

					send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
				}
			}

			// Keep sending away messages until we get a valid response
			if (!sink_received_away_reponse)
			{
				call AwaySenderTimer.startOneShot(get_away_delay());
			}			
		}
	}

	void Fake_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(rcvd, source_addr, source_distance);

		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			update_source_distance(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.min_sink_source_distance = min_sink_source_distance;
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
		case TailFakeNode:
		case PermFakeNode: Fake_receive_Normal(rcvd, source_addr); break;
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

		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			min_sink_source_distance = minbot(min_sink_source_distance, rcvd->sink_distance + 1);

			forwarding_message = *rcvd;
			forwarding_message.min_sink_source_distance = min_sink_source_distance;
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;

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

		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);

			if (rcvd->sink_distance == 0)
			{
				distance_neighbour_detail_t* neighbour = find_distance_neighbour(&neighbours, source_addr);

				if (neighbour == NULL || neighbour->contents.count == 0 ||
					min_source_distance == BOTTOM || min_neighbour_src_distance(neighbour) <= min_source_distance)
				{
					become_Fake(rcvd, TempFakeNode);

					// When receiving choose messages we do not want to reprocess this
					// away message.
					sequence_number_update(&choose_sequence_counter, rcvd->sequence_number);
				}
			}

			forwarding_message = *rcvd;
			forwarding_message.min_sink_source_distance = min_sink_source_distance;
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;

			extra_to_send = 1;
			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Away, Receive)
		case SinkNode: Sink_receive_Away(rcvd, source_addr); break;
		case SourceNode: Source_receive_Away(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Away(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Away)


	void Sink_receive_Choose(const ChooseMessage* const rcvd, am_addr_t source_addr)
	{
		sink_received_away_reponse = TRUE;
	}

	void Normal_receive_Choose(const ChooseMessage* const rcvd, am_addr_t source_addr)
	{
		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);
		sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);

		if (sequence_number_before(&choose_sequence_counter, rcvd->sequence_number))
		{
			distance_neighbours_t local_neighbours;

			sequence_number_update(&choose_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_CHOOSE(rcvd);

			find_neighbours_further_from_source(&local_neighbours);

			if (local_neighbours.size == 0)
			{
				become_Fake(rcvd, PermFakeNode);
			}
			else
			{
				//dbg("stdout", "Becoming a TFS because there is a node %u that can be next.\n", target);
				become_Fake(rcvd, TempFakeNode);
			}
		}
	}

	RECEIVE_MESSAGE_BEGIN(Choose, Receive)
		case SinkNode: Sink_receive_Choose(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Choose(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Choose)



	void Sink_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		sink_received_away_reponse = TRUE;

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			forwarding_message.min_sink_source_distance = min_sink_source_distance;

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);
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
		}
	}

	void Normal_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			forwarding_message.min_sink_source_distance = min_sink_source_distance;

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	void Fake_receive_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage forwarding_message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_FAKE(rcvd);

			forwarding_message.min_sink_source_distance = min_sink_source_distance;

			send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);
		}

		if ((
				(rcvd->message_type == PermFakeNode && type == PermFakeNode && pfs_can_become_normal()) ||
				(rcvd->message_type == TailFakeNode && type == PermFakeNode && pfs_can_become_normal()) ||
				(rcvd->message_type == PermFakeNode && type == TailFakeNode) ||
				(rcvd->message_type == TailFakeNode && type == TailFakeNode)
			) &&
			(
				(!dw_towards_source && (rcvd->sender_min_source_distance > min_source_distance ||
				(rcvd->sender_min_source_distance == min_source_distance && rcvd->source_id > TOS_NODE_ID)))
				||
				(dw_towards_source && (rcvd->sender_min_source_distance < min_source_distance ||
				(rcvd->sender_min_source_distance == min_source_distance && rcvd->source_id > TOS_NODE_ID)))
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


	void x_receieve_Beacon(const BeaconMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS_BEACON(rcvd, source_addr);

		METRIC_RCV_BEACON(rcvd);
	}

	RECEIVE_MESSAGE_BEGIN(Beacon, Receive)
		case SinkNode:
		case SourceNode:
		case NormalNode:
		case TempFakeNode:
		case TailFakeNode:
		case PermFakeNode: x_receieve_Beacon(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Fake)


	event uint32_t FakeMessageGenerator.calculatePeriod()
	{
		if (type == PermFakeNode || type == TailFakeNode)
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
		message->min_sink_source_distance = min_sink_source_distance;
		message->sink_distance = sink_distance;
		message->message_type = type;
		message->source_id = TOS_NODE_ID;
		message->sender_min_source_distance = min_source_distance;
	}

	event void FakeMessageGenerator.durationExpired(const AwayChooseMessage* original_message)
	{
		ChooseMessage message = *original_message;
		const fake_walk_result_t result = fake_walk_target();

		dbgverbose("stdout", "Finished sending Fake from TFS, now sending Choose to %u towards_source=%u.\n",
			result.target, result.towards_source);

		// When finished sending fake messages from a TFS

		message.min_sink_source_distance = min_sink_source_distance;
		message.sink_distance += 1;

		extra_to_send = 1;
		send_Choose_message(&message, result.target);

		if (type == PermFakeNode)
		{
			become_Normal();
		}
		else if (type == TempFakeNode)
		{
			dw_towards_source = result.towards_source;
			if (dw_towards_source) { call Leds.led0On(); } else { call Leds.led0Off(); }

			become_Fake(original_message, TailFakeNode);
		}
		else //if (type == TailFakeNode)
		{
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

		if (tosend != NULL)
		{
			METRIC_BCAST(Fake, result, tosend->sequence_number);
		}
		else
		{
			METRIC_BCAST(Fake, result, BOTTOM);
		}
	}
}
