#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"
#include "NeighbourDetail.h"

#include "AwayChooseMessage.h"
#include "FakeMessage.h"
#include "NormalMessage.h"
#include "BeaconMessage.h"
#include "InformMessage.h"

#include <CtpDebugMsg.h>
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
#define METRIC_RCV_BEACON(msg) METRIC_RCV(Beacon, source_addr, BOTTOM, UNKNOWN_SEQNO, BOTTOM)
#define METRIC_RCV_INFORM(msg) METRIC_RCV(Inform, source_addr, msg->source_id, UNKNOWN_SEQNO, msg->source_distance + 1)

// Basically a flat map between node ids to distances
typedef struct
{
	int16_t min_source_distance;

} distance_container_t;

static void distance_update(distance_container_t* __restrict find, distance_container_t const* __restrict given)
{
	find->min_source_distance = given->min_source_distance;
}

static void distance_print(const char* name, size_t n, am_addr_t address, distance_container_t const* contents)
{
	simdbg_clear(name, "[%u] => addr=%u min_source_distance=%d", n, address, contents->min_source_distance);
}

DEFINE_NEIGHBOUR_DETAIL(distance_container_t, distance, distance_update, distance_print, SLP_MAX_1_HOP_NEIGHBOURHOOD);

module SourceBroadcasterC
{
	provides interface CollectionDebug;

	uses interface Boot;
	uses interface Leds;
	uses interface Random;

	uses interface Timer<TMilli> as BroadcastNormalTimer;
	uses interface Timer<TMilli> as AwaySenderTimer;
	uses interface Timer<TMilli> as BeaconSenderTimer;
	uses interface Timer<TMilli> as InformSenderTimer;

	uses interface AMPacket;

	uses interface SplitControl as RadioControl;
	uses interface RootControl;
	uses interface StdControl as RoutingControl;

	uses interface Send as NormalSend;
	uses interface Receive as NormalReceive;
	uses interface Receive as NormalSnoop;
	uses interface Intercept as NormalIntercept;

	uses interface AMSend as AwaySend;
	uses interface Receive as AwayReceive;

	uses interface AMSend as ChooseSend;
	uses interface Receive as ChooseReceive;

	uses interface AMSend as FakeSend;
	uses interface Receive as FakeReceive;

	uses interface AMSend as BeaconSend;
	uses interface Receive as BeaconReceive;

	uses interface AMSend as InformSend;
	uses interface Receive as InformReceive;

	uses interface FakeMessageGenerator;
	uses interface ObjectDetector;

	uses interface SequenceNumbers as NormalSeqNos;

	// The distance between this node and each source
	uses interface Dictionary<am_addr_t, uint16_t> as SourceDistances;

	//uses interface CollectionPacket;
	//uses interface CtpInfo;
	//uses interface CtpCongestion;
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

	int16_t min_source_distance = BOTTOM;
	int16_t sink_distance = BOTTOM;

	bool sink_received_away_reponse = FALSE;

	bool first_normal_rcvd = FALSE;

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
		//assert(SOURCE_PERIOD_MS != BOTTOM);

		return SOURCE_PERIOD_MS / 2;
	}

	uint16_t estimated_number_of_sources(void)
	{
		return max(1, call SourceDistances.count());
	}

	bool node_is_sink(am_addr_t address)
	{
		return sink_id == address;
	}

	bool node_is_source(am_addr_t address)
	{
		return call SourceDistances.contains_key(address);
	}

	uint16_t get_dist_to_pull_back(void)
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
		const uint16_t distance = get_dist_to_pull_back();
		const uint16_t est_num_sources = estimated_number_of_sources();
		const uint32_t result = distance * est_num_sources;

		simdbg("stdout", "get_tfs_num_msg_to_send=%u (distance=%u, est_num_sources=%u)\n", result, distance, est_num_sources);

		return result;
	}

	uint32_t get_tfs_duration(void)
	{
		uint32_t duration = SOURCE_PERIOD_MS;

		if (sink_distance == BOTTOM || sink_distance <= 1)
		{
			duration -= get_away_delay();
		}

		simdbg("stdout", "get_tfs_duration=%u (sink_distance=%d)\n", duration, sink_distance);

		return duration;
	}

	uint32_t get_tfs_period(void)
	{
		const uint32_t duration = get_tfs_duration();
		const uint32_t msg = get_tfs_num_msg_to_send();
		const double period = duration / (double)msg;

		const uint32_t result_period = (uint32_t)ceil(period);

		simdbg("stdout", "get_tfs_period=%u\n", result_period);

		return result_period;
	}

	uint32_t get_pfs_period(void)
	{
		const double est_num_sources = estimated_number_of_sources();

		const double period_per_source = SOURCE_PERIOD_MS / est_num_sources;

		const uint32_t result_period = (uint32_t)ceil(period_per_source);

		simdbg("stdout", "get_pfs_period=%u (est_num_sources=%f)\n", result_period, est_num_sources);

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

		// Can't find node further from the source if we do not know our source distance
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

				// If this neighbours closest source is further than our closest source,
				// then we want to consider them for the next fake source.
				if (neighbour->contents.min_source_distance >= min_source_distance)
				{
					insert_distance_neighbour(local_neighbours, neighbour->address, &neighbour->contents);
				}
			}
		}
	}

	am_addr_t fake_walk_target(void)
	{
		am_addr_t result = AM_BROADCAST_ADDR;

		distance_neighbours_t local_neighbours;
		find_neighbours_further_from_source(&local_neighbours);	

		if (local_neighbours.size == 0 && min_source_distance == BOTTOM)
		{
			simdbgverbose("stdout", "No local neighbours to choose so broadcasting. (my-neighbours-size=%u)\n",
				neighbours.size); 
		}
		
		if (local_neighbours.size != 0)
		{
			// Choose a neighbour with equal probabilities.
			const uint16_t rnd = call Random.rand16();
			const uint16_t neighbour_index = rnd % local_neighbours.size;
			const distance_neighbour_detail_t* const neighbour = &local_neighbours.data[neighbour_index];

			result = neighbour->address;

#ifdef SLP_VERBOSE_DEBUG
			print_distance_neighbours("stdout", &local_neighbours);
#endif

			simdbgverbose("stdout", "Chosen %u at index %u (rnd=%u) out of %u neighbours\n",
				result, neighbour_index, rnd, local_neighbours.size);
		}

		return result;
	}

	void update_neighbours_beacon(const BeaconMessage* rcvd, am_addr_t source_addr)
	{
		distance_container_t dist;
		dist.min_source_distance = rcvd->neighbour_min_source_distance;
		insert_distance_neighbour(&neighbours, source_addr, &dist);
	}

	bool update_source_distance(am_addr_t source_id, uint16_t source_distance)
	{
		const uint16_t* distance = call SourceDistances.get(source_id);
		bool result = FALSE;

		if (distance == NULL || source_distance < *distance)
		{
			call SourceDistances.put(source_id, source_distance);
			result = TRUE;
		}

		if (min_source_distance == BOTTOM || min_source_distance > source_distance)
		{
			min_source_distance = source_distance;

			call BeaconSenderTimer.startOneShot(beacon_send_wait());
		}

		return result;
	}
	inline bool update_source_distance_normal(const NormalMessage* rcvd)
	{
		return update_source_distance(rcvd->source_id, rcvd->source_distance + 1);
	}
	inline bool update_source_distance_inform(const InformMessage* rcvd)
	{
		return update_source_distance(rcvd->source_id, rcvd->source_distance + 1);
	}

	void update_sink_distance(const AwayChooseMessage* rcvd, am_addr_t source_addr)
	{
		sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);
	}


	bool busy = FALSE;
	message_t packet;

	event void Boot.booted()
	{
		simdbgverbose("Boot", "%s: Application booted.\n", sim_time_string());

		sequence_number_init(&away_sequence_counter);
		sequence_number_init(&choose_sequence_counter);
		sequence_number_init(&fake_sequence_counter);

		if (TOS_NODE_ID == SINK_NODE_ID)
		{
			type = SinkNode;
			sink_distance = 0;
			call RootControl.setRoot();
			simdbg("Node-Change-Notification", "The node has become a Sink\n");
		}

		call RadioControl.start();
	}

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			simdbgverbose("SourceBroadcasterC", "%s: RadioControl started.\n", sim_time_string());

			// Wait for 2 seconds before detecting source to allow the CTP to set up
			call ObjectDetector.start_later(3 * 1000);

			call RoutingControl.start();
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

			call InformSenderTimer.startOneShot(500);

			call BroadcastNormalTimer.startOneShot(1000 + SOURCE_PERIOD_MS);
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

	USE_MESSAGE_NO_TARGET(Normal);
	USE_MESSAGE(Away);
	USE_MESSAGE(Choose);
	USE_MESSAGE(Fake);
	USE_MESSAGE(Beacon);
	USE_MESSAGE(Inform);

	void become_Normal(void)
	{
		const char* const old_type = type_to_string();

		type = NormalNode;

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
			call FakeMessageGenerator.startRepeated(message, get_tfs_duration() / estimated_number_of_sources());
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

		if (send_Normal_message(&message))
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
		message.algorithm = ALGORITHM;

		sequence_number_increment(&away_sequence_counter);

		extra_to_send = 2;
		send_Away_message(&message, AM_BROADCAST_ADDR);
	}

	event void BeaconSenderTimer.fired()
	{
		BeaconMessage message;
		bool result;

		simdbgverbose("stdout", "%s: BeaconSenderTimer fired.\n", sim_time_string());

		if (busy)
		{
			simdbgverbose("stdout", "Device is busy rescheduling beaconing\n");
			call BeaconSenderTimer.startOneShot(beacon_send_wait());
			return;
		}

		message.neighbour_min_source_distance = min_source_distance;

		message.sink_distance = sink_distance;

		result = send_Beacon_message(&message, AM_BROADCAST_ADDR);
		if (!result)
		{
			simdbgverbose("stdout", "Send failed rescheduling beaconing\n");
			call BeaconSenderTimer.startOneShot(beacon_send_wait());
		}
	}


	event void InformSenderTimer.fired()
	{
		InformMessage message;
		bool result;

		simdbgverbose("stdout", "%s: InformSenderTimer fired.\n", sim_time_string());

		if (busy)
		{
			simdbgverbose("stdout", "Device is busy rescheduling inform\n");
			call InformSenderTimer.startOneShot(beacon_send_wait());
			return;
		}
		
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;

		result = send_Inform_message(&message, AM_BROADCAST_ADDR);
		if (!result)
		{
			simdbgverbose("stdout", "Send failed rescheduling inform\n");
			call InformSenderTimer.startOneShot(beacon_send_wait());
		}
	}


	void Sink_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			update_source_distance_normal(rcvd);

			if (!first_normal_rcvd)
			{
				first_normal_rcvd = TRUE;
				call Leds.led1On();
			}

			// Keep sending away messages until we get a valid response
			if (!sink_received_away_reponse)
			{
				call AwaySenderTimer.startOneShot(get_away_delay());
			}
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SinkNode: Sink_receive_Normal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)


	void x_snoop_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		update_source_distance_normal(rcvd);

		/*if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			//simdbgverbose("stdout", "%s: Normal Snooped unseen Normal data=%u seqno=%u srcid=%u from %u.\n",
			//	sim_time_string(), rcvd->sequence_number, rcvd->source_id, source_addr);
		}*/
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Snoop)
		case SourceNode: break;
		case SinkNode: break;
		case TempFakeNode:
		case TailFakeNode:
		case PermFakeNode:
		case NormalNode: x_snoop_Normal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)


	bool x_intercept_Normal(NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			update_source_distance_normal(rcvd);

			if (!first_normal_rcvd)
			{
				first_normal_rcvd = TRUE;
				call Leds.led1On();
			}

			rcvd->source_distance += 1;
		}

		return TRUE;
	}

	INTERCEPT_MESSAGE_BEGIN(Normal, Intercept)
		case SourceNode: break;
		case SinkNode: break;
		case TempFakeNode:
		case TailFakeNode:
		case PermFakeNode:
		case NormalNode: return x_intercept_Normal(rcvd, source_addr);
	INTERCEPT_MESSAGE_END(Normal)






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

		simdbg("stdout", "received away message seqno=%u\n", rcvd->sequence_number);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			update_sink_distance(rcvd, source_addr);

			if (rcvd->sink_distance == 0) // Received from sink
			{
				const distance_neighbour_detail_t* neighbour = find_distance_neighbour(&neighbours, source_addr);
				const int16_t neighbour_min_source_distance = neighbour == NULL ? BOTTOM : neighbour->contents.min_source_distance;

				if (min_source_distance == BOTTOM ||
					neighbour_min_source_distance == BOTTOM ||
					neighbour_min_source_distance <= min_source_distance)
				{
					become_Fake(rcvd, TempFakeNode);

					// When receiving choose messages we do not want to reprocess this
					// away message.
					sequence_number_update(&choose_sequence_counter, rcvd->sequence_number);
				}
			}

			forwarding_message = *rcvd;
			forwarding_message.sink_distance += 1;
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
		case TempFakeNode:
		case TailFakeNode:
		case PermFakeNode: break;
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
		sink_received_away_reponse = TRUE;

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

			METRIC_RCV_FAKE(rcvd);

			// Do not want source nodes to forward fake messages, as that would lead
			// attackers to be drawn towards them!
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
				rcvd->sender_min_source_distance > min_source_distance ||
				(rcvd->sender_min_source_distance == min_source_distance && rcvd->source_id > TOS_NODE_ID)
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
		update_neighbours_beacon(rcvd, source_addr);

		METRIC_RCV_BEACON(rcvd);

		sink_distance = minbot(sink_distance, botinc(rcvd->sink_distance));
	}

	RECEIVE_MESSAGE_BEGIN(Beacon, Receive)
		case SinkNode:
		case SourceNode:
		case NormalNode:
		case TempFakeNode:
		case TailFakeNode:
		case PermFakeNode: x_receive_Beacon(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Beacon)



	void x_receive_Inform(const InformMessage* const rcvd, am_addr_t source_addr)
	{
		simdbg("stdout", "Received inform from %u via %u walked %u\n", rcvd->source_id, source_addr, rcvd->source_distance);

		if (update_source_distance_inform(rcvd))
		{
			InformMessage forwarding_message = *rcvd;

			METRIC_RCV_INFORM(rcvd);

			simdbg("stdout", "Forwarding inform (srcdist of %u is %u)\n", rcvd->source_id, *call SourceDistances.get(rcvd->source_id));

			forwarding_message.source_distance += 1;

			send_Inform_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Inform, Receive)
		case SinkNode:
		case SourceNode:
		case NormalNode:
		case TempFakeNode:
		case TailFakeNode:
		case PermFakeNode: x_receive_Inform(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Inform)



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
		message->sender_sink_distance = sink_distance;
		message->message_type = type;
		message->source_id = TOS_NODE_ID;
		message->sender_min_source_distance = min_source_distance;
	}

	event void FakeMessageGenerator.durationExpired(const AwayChooseMessage* original_message)
	{
		ChooseMessage message = *original_message;
		const am_addr_t target = fake_walk_target();

		simdbgverbose("stdout", "Finished sending Fake from TFS, now sending Choose to %u.\n", target);

		// When finished sending fake messages from a TFS

		message.sink_distance += 1;

		extra_to_send = 2;
		send_Choose_message(&message, target);

		if (type == PermFakeNode)
		{
			become_Normal();
		}
		else if (type == TempFakeNode)
		{
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
			METRIC_BCAST(Fake, result, UNKNOWN_SEQNO);
		}
	}


	// The following is simply for metric gathering.
	// The CTP debug events are hooked into so we have correctly record when a message has been sent.

	command error_t CollectionDebug.logEvent(uint8_t event_type) {
		//simdbg("stdout", "logEvent %u\n", event_type);
		return SUCCESS;
	}
	command error_t CollectionDebug.logEventSimple(uint8_t event_type, uint16_t arg) {
		//simdbg("stdout", "logEventSimple %u %u\n", event_type, arg);
		return SUCCESS;
	}
	command error_t CollectionDebug.logEventDbg(uint8_t event_type, uint16_t arg1, uint16_t arg2, uint16_t arg3) {
		//simdbg("stdout", "logEventDbg %u %u %u %u\n", event_type, arg1, arg2, arg3);
		return SUCCESS;
	}
	command error_t CollectionDebug.logEventMsg(uint8_t event_type, uint16_t msg, am_addr_t origin, am_addr_t node) {
		//simdbg("stdout", "logEventMessage %u %u %u %u\n", event_type, msg, origin, node);

		if (event_type == NET_C_FE_SENDDONE_WAITACK || event_type == NET_C_FE_SENT_MSG || event_type == NET_C_FE_FWD_MSG)
		{
			// TODO: FIXME
			// Likely to be double counting Normal message broadcasts due to METRIC_BCAST in send_Normal_message
			METRIC_BCAST(Normal, "success", UNKNOWN_SEQNO);
		}

		return SUCCESS;
	}
	command error_t CollectionDebug.logEventRoute(uint8_t event_type, am_addr_t parent, uint8_t hopcount, uint16_t metric) {
		//simdbg("stdout", "logEventRoute %u %u %u %u\n", event_type, parent, hopcount, metric);

		if (event_type == NET_C_TREE_SENT_BEACON)
		{
			METRIC_BCAST(CTPBeacon, "success", UNKNOWN_SEQNO);
		}

		else if (event_type == NET_C_TREE_RCV_BEACON)
		{
			METRIC_RCV(CTPBeacon, parent, BOTTOM, UNKNOWN_SEQNO, BOTTOM);
		}

		return SUCCESS;
	}
}
