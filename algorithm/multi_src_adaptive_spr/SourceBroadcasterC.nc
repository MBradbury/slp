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

#define EWMA_FACTOR (0.5f)

// Basically a flat map between node ids to distances
typedef struct
{
	uint16_t node[SLP_MAX_1_HOP_NEIGHBOURHOOD];
	int16_t src_distance[SLP_MAX_1_HOP_NEIGHBOURHOOD];
	uint16_t count;

	int16_t sink_distance;

} distance_container_t;

static void distance_update(distance_container_t* __restrict find, distance_container_t const* __restrict given)
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
				break;
			}
		}

		// Couldn't find distance, so add it
		if (j == find->count)
		{
			find->node[find->count] = given->node[i];
			find->src_distance[find->count] = given->src_distance[i];
			find->count++;
		}
	}

	find->sink_distance = minbot(find->sink_distance, given->sink_distance);
}

static void distance_print(const char* name, size_t n, am_addr_t address, distance_container_t const* contents)
{
	uint16_t i;

	simdbg_clear(name, "[%u] => addr=%u dsrc={", n, address);

	for (i = 0; i != contents->count; ++i)
	{
		simdbg_clear(name, "%u: %d", contents->node[i], contents->src_distance[i]);

		if (i + 1 != contents->count)
		{
			simdbg_clear(name, ", ");
		}
	}

	simdbg_clear(name, "} dsink=%d", contents->sink_distance);
}

DEFINE_NEIGHBOUR_DETAIL(distance_container_t, distance, distance_update, distance_print, SLP_MAX_1_HOP_NEIGHBOURHOOD);

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

#define UPDATE_NEIGHBOURS_AWAYCHOOSE(rcvd, source_addr) \
{ \
	distance_container_t dist; \
	dist.count = 0; \
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

	// The distance between this node and each source
	uses interface Dictionary<am_addr_t, float> as SourceDistances;

	// The distance between the recorded source and the sink
	uses interface Dictionary<am_addr_t, float> as SinkSourceDistances;
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

	am_addr_t sink_id = AM_BROADCAST_ADDR;

	distance_neighbours_t neighbours;

	SequenceNumber away_sequence_counter;
	SequenceNumber choose_sequence_counter;
	SequenceNumber fake_sequence_counter;

	SequenceNumber source_fake_sequence_counter;
	uint32_t source_fake_sequence_increments;

	uint32_t normal_sequence_increments = 0;

	int16_t min_sink_source_distance = BOTTOM;
	int16_t min_source_distance = BOTTOM;
	float sink_distance = BOTTOM;

	bool sink_received_away_reponse = FALSE;

	bool first_normal_rcvd = FALSE;

	DirectedRandomWalkDirection drw_direction = DirectedWalkDirectionUnknown;

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

	// Exponentially weighted moving average
	// a higher factor discounts older information faster
	float ewma(float factor, float history, float current)
	{
		if (history < 0 && current < 0)
		{
			return BOTTOM;
		}
		else if (history < 0 && current >= 0)
		{
			return current;
		}
		else if (history >= 0 && current < 0)
		{
			return history;
		}
		else
		{
			return factor * current + (1.0 - factor) * history;
			//return (current < history) ? current : history;
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

	uint32_t get_away_delay(void)
	{
		//assert(SOURCE_PERIOD_MS != BOTTOM);

		return SOURCE_PERIOD_MS / 2;
	}

	uint16_t estimated_number_of_sources(void)
	{
		return max(1, call SourceDistances.count());
	}

	bool node_within_towards_source_limit(void)
	{
		return sink_distance <= (min_sink_source_distance/2.0 - 1);
	}

	bool node_at_towards_source_limit(void)
	{
		return fabs(sink_distance - (min_sink_source_distance/2.0 - 1)) <= 1e-6;
	}

	bool node_is_sink(am_addr_t address)
	{
		return sink_id == address;
	}

	bool node_is_source(am_addr_t address)
	{
		return call SourceDistances.contains_key(address);
	}

	uint32_t get_dist_to_pull_back(void)
	{
		// PB_FIXED2_APPROACH worked quite well, so lets stick to it
		return 2;
	}

	double inclination_angle_rad(am_addr_t source_id)
	{
		const double ssd = call SinkSourceDistances.get_or_default(source_id, BOTTOM);
		const double dsrc = call SourceDistances.get_or_default(source_id, BOTTOM);
		const double dsink = sink_distance;
		double temp, angle;

		if (ssd < 0 || dsrc <= 0 || dsink <= 0)
		{
			//simdbg("stdout", "source_id=%u ssd=%f dsrc=%f dsink=%f\n", source_id, ssd, dsrc, dsink);
			return INFINITY;
		}

		temp = ((dsrc * dsrc) + (dsink * dsink) - (ssd * ssd)) / (2.0 * dsrc * dsink);
		angle = acos(temp);

		//simdbg("stdout", "source_id=%u ssd=%f dsrc=%f dsink=%f inter=%f angle=%f\n", source_id, ssd, dsrc, dsink, temp, rad2deg(angle));

		return angle;
	}

	bool invalid_double(double x)
	{
		return isinf(x) || isnan(x) || x < 0.0 || x > M_PI;
	}

	double angle_when_node_further_than_sink(am_addr_t source1, am_addr_t source2)
	{
		const double source1_angle = inclination_angle_rad(source1);
		const double source2_angle = inclination_angle_rad(source2);
		double result;

		if (invalid_double(source1_angle) || invalid_double(source2_angle))
		{
			//simdbg("stdout", "further result invalid\n");
			return INFINITY;
		}

		result = source1_angle + source2_angle;

		//simdbg("stdout", "further result %f\n", result);

		return result;
	}

	double angle_when_node_closer_than_sink(am_addr_t source1, am_addr_t source2)
	{
		const double source1_angle = inclination_angle_rad(source1);
		const double source2_angle = inclination_angle_rad(source2);
		double result;

		if (invalid_double(source1_angle) || invalid_double(source2_angle))
		{
			//simdbg("stdout", "closer result invalid\n");
			return INFINITY;
		}

		result = 2.0 * M_PI - source1_angle - source2_angle;

		//simdbg("stdout", "closer result %f\n", result);

		return result;
	}

	double angle_when_node_side_of_sink(am_addr_t source1, am_addr_t source2)
	{
		const double source1_angle = inclination_angle_rad(source1);
		const double source2_angle = inclination_angle_rad(source2);
		double result;

		if (invalid_double(source1_angle) || invalid_double(source2_angle))
		{
			//simdbg("stdout", "side result invalid\n");
			return INFINITY;
		}

		// Covers both a1 - a2 and a2 - a1 depending on which angle is the largest.
		result = fabs(source1_angle - source2_angle);

		//simdbg("stdout", "side result %f\n", result);

		return result;
	}

	double interference_strategy(am_addr_t source1, am_addr_t source2)
	{
#if defined(NO_INTERFERENCE_APPROACH)
		return 0;
#elif defined(ALWAYS_FURTHER_APPORACH)
		return angle_when_node_further_than_sink(source1, source2);
#elif defined(ALWAYS_CLOSER_APPORACH)
		return angle_when_node_closer_than_sink(source1, source2);
#elif defined(ALWAYS_SIDE_APPORACH)
		return angle_when_node_side_of_sink(source1, source2);
#elif defined(MIN_VALID_APPROACH)
		const double further = angle_when_node_further_than_sink(source1, source2);
		const double closer = angle_when_node_closer_than_sink(source1, source2);
		const double side = angle_when_node_side_of_sink(source1, source2);

		const double angles[] = { further, closer, side };
		double min_angle = 1 * M_PI;
		bool found_min = FALSE;
		unsigned int i;

		for (i = 0; i != ARRAY_SIZE(angles); ++i)
		{
			if (!invalid_double(angles[i]) && angles[i] < min_angle)
			{
				min_angle = angles[i];
				found_min = TRUE;
			}
		}

		return found_min ? min_angle : 0.0;
#else
#	error "No apporach specified"
#endif
	}

	double angle_factor(am_addr_t source_id)
	{
		const am_addr_t* iter;
		double factor = 1.0;
		double intermediate_angle;
		double non_interference;

		for (iter = call SourceDistances.beginKeys(); iter != call SourceDistances.endKeys(); ++iter)
		{
			if (*iter == source_id)
				continue;

			intermediate_angle = interference_strategy(source_id, *iter);

			//simdbg("stdout", "angle between %u and %u is %f\n", source_id, *iter, rad2deg(intermediate_angle));

			// Skip messed up results, lets just assume the worst in these cases
			if (invalid_double(intermediate_angle))
				continue;

			// When cooperating this will be 1, when completely interfering this will be 0
			non_interference = 1.0 - (intermediate_angle / M_PI);

			factor *= non_interference;
		}

		return factor;
	}

	double all_source_factor(void)
	{
		double factor = 0.0;

		const am_addr_t* iter;
		for (iter = call SourceDistances.beginKeys(); iter != call SourceDistances.endKeys(); ++iter)
		{
			factor += angle_factor(*iter);
		}

		//simdbg("stdout", "all_source_factor=%f\n", factor);

		return factor;
	}

	double get_nodes_Normal_receive_ratio(void)
	{
		uint64_t total_sent = 1;
		SequenceNumber* iter;
		for (iter = call NormalSeqNos.begin(); iter != call NormalSeqNos.end(); ++iter)
		{
			total_sent += *iter;
		}

		return (normal_sequence_increments + 1) / (double)total_sent;
	}

	double get_sources_Fake_receive_ratio(void)
	{
		// Need to add one here because it is possible for the values to both be 0
		// if no fake messages have ever been received.
		const uint32_t seq_inc = source_fake_sequence_increments + 1;
		const uint32_t counter = sequence_number_get(&source_fake_sequence_counter) + 1;

		return seq_inc / (double)counter;
	}

	uint32_t get_tfs_num_msg_to_send(void)
	{
		const uint32_t distance = get_dist_to_pull_back();
		const uint16_t est_num_sources = estimated_number_of_sources();

		//simdbgverbose("stdout", "get_tfs_num_msg_to_send=%u, (Dsrc=%d, Dsink=%f, Dss=%d)\n",
		//	distance, source_distance, sink_distance, min_sink_source_distance);

		return distance * est_num_sources;
	}

	uint32_t get_tfs_duration(void)
	{
		uint32_t duration = SOURCE_PERIOD_MS;

		if (sink_distance <= 1)
		{
			duration -= get_away_delay();
		}

		simdbgverbose("stdout", "get_tfs_duration=%u (sink_distance=%f)\n", duration, sink_distance);

		return duration;
	}

	uint32_t get_tfs_period(void)
	{
		const uint32_t duration = get_tfs_duration();
		const uint32_t msg = get_tfs_num_msg_to_send();
		const double period = duration / (double)msg;
		//const double est_num_sources = estimated_number_of_sources();
		const double fake_rcv_ratio_at_src = get_sources_Fake_receive_ratio();
		//const double normal_rcv_ratio = get_nodes_Normal_receive_ratio();

		const uint32_t result_period = (uint32_t)ceil(period * fake_rcv_ratio_at_src);

		//simdbg("stdout", "get_tfs_period=%u\n", result_period);

		return result_period;
	}

	uint32_t get_pfs_period(void)
	{
		const double fake_rcv_ratio_at_src = get_sources_Fake_receive_ratio();

		const double est_num_sources = all_source_factor();
		//const double normal_rcv_ratio = get_nodes_Normal_receive_ratio();

		const double period_per_source = SOURCE_PERIOD_MS / est_num_sources;

		const uint32_t result_period = (uint32_t)ceil(period_per_source * fake_rcv_ratio_at_src);

		//simdbg("stdout", "get_pfs_period=%u fakercv=%f normrcv=%f\n",
		//	result_period, fake_rcv_ratio_at_src, normal_rcv_ratio);

		return result_period;
	}

	uint32_t beacon_send_wait(void)
	{
		return 75U + (uint32_t)(50U * random_float());
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

				// Skip sink or sources as we do not want them to become fake nodes
				if (node_is_sink(neighbour->address) || node_is_source(neighbour->address))
				{
					continue;
				}

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

			// Skip sink or sources as we do not want them to become fake nodes
			if (node_is_sink(neighbour->address) || node_is_source(neighbour->address))
			{
				continue;
			}

			max_sink_distance = max(max_sink_distance, neighbour->contents.sink_distance);
		}

		for (i = 0; i != neighbours.size; ++i)
		{
			distance_neighbour_detail_t const* const neighbour = &neighbours.data[i];

			// Skip sink or sources as we do not want them to become fake nodes
			if (node_is_sink(neighbour->address) || node_is_source(neighbour->address))
			{
				continue;
			}

			if (max_sink_distance == neighbour->contents.sink_distance)
			{
				insert_distance_neighbour(local_neighbours, neighbour->address, &neighbour->contents);
			}
		}

		return max_sink_distance;
	}

	typedef struct {
		am_addr_t target;
		DirectedRandomWalkDirection drw_direction;
	} fake_walk_result_t;

	// TODO: modify this to allow the directed random walk to go closer to the source
	// + (min_sink_source_distance / 2)
	// Will also need to modify TailFS reverting to Normal, as it will need to be able
	// to detect that the TFS that is closer to the source is part of the walk and a valid option
	fake_walk_result_t fake_walk_target(DirectedRandomWalkDirection drw_direction_hint)
	{
		fake_walk_result_t result = { AM_BROADCAST_ADDR, DirectedWalkDirectionUnknown };
		//am_addr_t chosen_address = AM_BROADCAST_ADDR;
		//bool towards_source = FALSE;

		distance_neighbours_t local_neighbours;
		init_distance_neighbours(&local_neighbours);

		if (drw_direction_hint != DirectedWalkTowardsSource)
		{
			find_neighbours_further_from_source(&local_neighbours);
		}	

		if (local_neighbours.size == 0 && min_source_distance == BOTTOM)
		{
			simdbgverbose("stdout", "No local neighbours to choose so broadcasting. (my-neighbours-size=%u)\n",
				neighbours.size); 
		}
		else if (local_neighbours.size == 0 && neighbours.size != 0)
		{
			// There are neighbours who exist that are closer to the source than this node.
			// We should consider moving to one of these neighbours if we are still close to the sink.

			simdbgverbose("stdout", "Considering allowing fake sources to move towards the source\n");
			simdbgverbose("stdout", "sink-distance=%f <= min-sink-distance/2=%d\n", sink_distance, (min_sink_source_distance / 2));

			if (node_within_towards_source_limit())
			{
				const uint16_t max_sink_distance = find_neighbours_with_max_sink_distance(&local_neighbours);

				if (local_neighbours.size != 0)
				{
					result.drw_direction = DirectedWalkTowardsSource;
				}

				simdbgverbose("stdout", "Found %d neighbours with max_sink_distance=%d\n", local_neighbours.size, max_sink_distance);
				simdbgverbose("stdout", "drw-direction=%d\n", result.drw_direction);
			}
		}
		else
		{
			result.drw_direction = DirectedWalkAwaySource;
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

			simdbgverbose("stdout", "Chosen %u at index %u (rnd=%u) out of %u neighbours\n",
				result.target, neighbour_index, rnd, local_neighbours.size);
		}

		return result;
	}

	void update_source_distance(const NormalMessage* rcvd)
	{
		const float* distance = call SourceDistances.get(rcvd->source_id);
		const float* sink_source_distance = call SinkSourceDistances.get(rcvd->source_id);

		if (distance == NULL)
		{
			call SourceDistances.put(rcvd->source_id, rcvd->source_distance + 1);
			
			// Our source distance has been set for the first time, so we need to inform neighbours
			call BeaconSenderTimer.startOneShot(beacon_send_wait());
		}
		else
		{
			const float existing_distance = *distance;

			call SourceDistances.put(rcvd->source_id, ewma(EWMA_FACTOR, *distance, rcvd->source_distance + 1));

			/*if (fabs(*distance - existing_distance) > 0.95f)
			{
				// Our source distance has changed, so we want to inform neighbours
				// However, we should only do this if a big change has occurred!
				// TODO: only do this some times
				call BeaconSenderTimer.startOneShot(beacon_send_wait());
			}*/
		}

		min_source_distance = minbot(min_source_distance, rcvd->source_distance + 1);

		if (rcvd->sink_distance != BOTTOM)
		{
			if (sink_source_distance == NULL)
			{
				//simdbg("stdout", "Updating sink distance of %u to %d\n", rcvd->source_id, rcvd->sink_distance);
				call SinkSourceDistances.put(rcvd->source_id, rcvd->sink_distance);
			}
			else
			{
				call SinkSourceDistances.put(rcvd->source_id, ewma(EWMA_FACTOR, *sink_source_distance, rcvd->sink_distance));
			}
		}
	}

	void update_sink_distance(const AwayChooseMessage* rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS_AWAYCHOOSE(rcvd, source_addr);

		sink_distance = ewma(EWMA_FACTOR, sink_distance, rcvd->sink_distance + 1);

		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		// Probably don't need to send a beacon here.
		// The forwarding of the Away message should update our neighbours correctly.
	}


	bool busy = FALSE;
	message_t packet;

	event void Boot.booted()
	{
		simdbgverbose("Boot", "%s: Application booted.\n", sim_time_string());

		sequence_number_init(&away_sequence_counter);
		sequence_number_init(&choose_sequence_counter);
		sequence_number_init(&fake_sequence_counter);

		source_fake_sequence_increments = 0;
		sequence_number_init(&source_fake_sequence_counter);

		if (TOS_NODE_ID == SINK_NODE_ID)
		{
			type = SinkNode;
			sink_distance = 0;
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

			simdbg_clear("Metric-SOURCE_CHANGE", "unset,%u\n", TOS_NODE_ID);
			simdbg("Node-Change-Notification", "The node has become a Normal\n");
		}
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

		drw_direction = DirectedWalkDirectionUnknown;
		if (drw_direction == DirectedWalkTowardsSource) { call Leds.led2On(); } else { call Leds.led2Off(); }

		call FakeMessageGenerator.stop();

		simdbg("Fake-Notification", "The node has become a %s was %s\n", type_to_string(), old_type);
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

		simdbg("Fake-Notification", "The node has become a %s was %s\n", type_to_string(), old_type);

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

		simdbgverbose("SourceBroadcasterC", "%s: BroadcastNormalTimer fired.\n", sim_time_string());

		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;
		message.min_sink_source_distance = min_sink_source_distance;
		message.sink_distance = sink_distance;

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
		message.drw_direction = DirectedWalkDirectionUnknown;

		sequence_number_increment(&away_sequence_counter);

		extra_to_send = 2;
		send_Away_message(&message, AM_BROADCAST_ADDR);
	}

	event void BeaconSenderTimer.fired()
	{
		BeaconMessage message;
		uint16_t* iter;
		uint16_t i;
		bool result;

		simdbgverbose("stdout", "%s: BeaconSenderTimer fired.\n", sim_time_string());

		if (busy)
		{
			simdbgverbose("stdout", "Device is busy rescheduling beaconing\n");
			call BeaconSenderTimer.startOneShot(beacon_send_wait());
			return;
		}

		// Send all known source distances in the beacon message

		message.count = call SourceDistances.count();

		for (iter = call SourceDistances.beginKeys(), i = 0; iter != call SourceDistances.endKeys(); ++iter, ++i)
		{
			message.node[i] = *iter;
			message.src_distance[i] = (int16_t)round(*call SourceDistances.get_from_iter(iter));
		}

		message.sink_distance = (int16_t)round(sink_distance);

		//call Packet.clear(&packet);

		result = send_Beacon_message(&message, AM_BROADCAST_ADDR);
		if (!result)
		{
			simdbgverbose("stdout", "Send failed rescheduling beaconing\n");
			call BeaconSenderTimer.startOneShot(beacon_send_wait());
		}
	}


	void Normal_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			++normal_sequence_increments;

			update_source_distance(rcvd);

			if (!first_normal_rcvd)
			{
				first_normal_rcvd = TRUE;
				call Leds.led1On();
			}

			forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;
			forwarding_message.min_sink_source_distance = min_sink_source_distance;
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

			++normal_sequence_increments;

			update_source_distance(rcvd);

			min_sink_source_distance = minbot(min_sink_source_distance, rcvd->source_distance + 1);

			if (!first_normal_rcvd)
			{
				first_normal_rcvd = TRUE;
				call Leds.led1On();

				// Having the sink forward the normal message helps set up
				// the source distance gradients.
				// However, we don't want to keep doing this as it benefits the attacker.
				{
					NormalMessage forwarding_message = *rcvd;
					forwarding_message.source_distance += 1;
					forwarding_message.min_sink_source_distance = min_sink_source_distance;
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
		min_sink_source_distance = minbot(min_sink_source_distance, rcvd->min_sink_source_distance);

		source_fake_sequence_counter = max(source_fake_sequence_counter, rcvd->fake_sequence_number);
		source_fake_sequence_increments = max(source_fake_sequence_increments, rcvd->fake_sequence_increments);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			++normal_sequence_increments;

			update_source_distance(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;
			forwarding_message.min_sink_source_distance = min_sink_source_distance;
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

		call BeaconSenderTimer.startOneShot(beacon_send_wait());
	}

	void Source_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_id = rcvd->source_id;

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			update_sink_distance(rcvd, source_addr);

			forwarding_message = *rcvd;
			forwarding_message.sink_distance += 1;
			forwarding_message.min_sink_source_distance = min_sink_source_distance;
			forwarding_message.algorithm = algorithm;

			extra_to_send = 1;
			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);

			call BeaconSenderTimer.startOneShot(beacon_send_wait());
		}
	}

	void Normal_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_id = rcvd->source_id;

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			update_sink_distance(rcvd, source_addr);

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
			forwarding_message.sink_distance += 1;
			forwarding_message.min_sink_source_distance = min_sink_source_distance;
			forwarding_message.algorithm = algorithm;

			extra_to_send = 1;
			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);

			call BeaconSenderTimer.startOneShot(beacon_send_wait());
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

		if (sequence_number_before(&choose_sequence_counter, rcvd->sequence_number))
		{
			distance_neighbours_t local_neighbours;

			sequence_number_update(&choose_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_CHOOSE(rcvd);

			update_sink_distance(rcvd, source_addr);

			if (rcvd->drw_direction == DirectedWalkTowardsSource)
			{
				drw_direction = rcvd->drw_direction;
				if (drw_direction == DirectedWalkTowardsSource) { call Leds.led2On(); } else { call Leds.led2Off(); }
			}
			else
			{
				find_neighbours_further_from_source(&local_neighbours);
			}

			if ((drw_direction != DirectedWalkTowardsSource || node_at_towards_source_limit()) && local_neighbours.size == 0)
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
				(drw_direction != DirectedWalkTowardsSource && (rcvd->sender_min_source_distance > min_source_distance ||
				(rcvd->sender_min_source_distance == min_source_distance && rcvd->source_id > TOS_NODE_ID)))
				||
				(drw_direction == DirectedWalkTowardsSource && (rcvd->sender_min_source_distance < min_source_distance || rcvd->sender_sink_distance > sink_distance ||
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


	void x_receive_Beacon(const BeaconMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS_BEACON(rcvd, source_addr);

		METRIC_RCV_BEACON(rcvd);

		sink_distance = ewma(EWMA_FACTOR, sink_distance, botinc(rcvd->sink_distance));
	}

	RECEIVE_MESSAGE_BEGIN(Beacon, Receive)
		case SinkNode:
		case SourceNode:
		case NormalNode:
		case TempFakeNode:
		case TailFakeNode:
		case PermFakeNode: x_receive_Beacon(rcvd, source_addr); break;
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
			simdbgerror("stdout", "Called FakeMessageGenerator.calculatePeriod on non-fake node.\n");
			return 0;
		}
	}

	event void FakeMessageGenerator.generateFakeMessage(FakeMessage* message)
	{
		message->sequence_number = sequence_number_next(&fake_sequence_counter);
		message->min_sink_source_distance = min_sink_source_distance;
		message->sender_sink_distance = sink_distance;
		message->message_type = type;
		message->source_id = TOS_NODE_ID;
		message->sender_min_source_distance = min_source_distance;
	}

	event void FakeMessageGenerator.durationExpired(const AwayChooseMessage* original_message)
	{
		ChooseMessage message = *original_message;
		const fake_walk_result_t result = fake_walk_target(original_message->drw_direction);

		simdbgverbose("stdout", "Finished sending Fake from TFS, now sending Choose to %u towards_source=%u.\n",
			result.target, result.drw_direction);

		// When finished sending fake messages from a TFS

		message.min_sink_source_distance = min_sink_source_distance;
		message.sink_distance += 1;
		message.drw_direction = result.drw_direction;

		extra_to_send = 1;
		send_Choose_message(&message, result.target);

		if (type == PermFakeNode)
		{
			become_Normal();
		}
		else if (type == TempFakeNode)
		{
			drw_direction = result.drw_direction;
			if (drw_direction == DirectedWalkTowardsSource) { call Leds.led2On(); } else { call Leds.led2Off(); }

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

		simdbgverbose("SourceBroadcasterC", "Sent Fake with error=%u.\n", error);

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
