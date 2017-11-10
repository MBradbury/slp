#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"
#include "NeighbourDetail.h"

#include "AwayMessage.h"
#include "FakeMessage.h"
#include "NormalMessage.h"
#include "DummyNormalMessage.h"
#include "BeaconMessage.h"

#include <Timer.h>
#include <TinyError.h>

// Notes:
/*
 * Important to remember that the algorithm cannot rely on the first flood to get the minimum distance,
 * this is because nodes will now flood at exactly the same time.
 * So we will need to maintain and update neighbours of a change in our source distances
 */

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, msg->sink_distance + 1)
#define METRIC_RCV_FAKE(msg) METRIC_RCV(Fake, source_addr, msg->source_id, msg->sequence_number, BOTTOM)
#define METRIC_RCV_DUMMYNORMAL(msg) METRIC_RCV(DummyNormal, source_addr, BOTTOM, BOTTOM, BOTTOM)
#define METRIC_RCV_BEACON(msg) METRIC_RCV(Beacon, source_addr, BOTTOM, BOTTOM, BOTTOM)

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
	uses interface Boot;
	uses interface Leds;
	uses interface Random;

	uses interface Timer<TMilli> as BroadcastNormalTimer;
	uses interface Timer<TMilli> as AwaySenderTimer;
	uses interface Timer<TMilli> as BeaconSenderTimer;
	uses interface Timer<TMilli> as DummyNormalSenderTimer;

	uses interface Packet;
	uses interface AMPacket;

	uses interface SplitControl as RadioControl;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;

	uses interface AMSend as AwaySend;
	uses interface Receive as AwayReceive;

	uses interface AMSend as FakeSend;
	uses interface Receive as FakeReceive;

	uses interface AMSend as DummyNormalSend;
	uses interface Receive as DummyNormalReceive;

	uses interface AMSend as BeaconSend;
	uses interface Receive as BeaconReceive;

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
	uses interface Dictionary<am_addr_t, uint16_t> as SinkSourceDistances;
}

implementation
{
	enum
	{
		SourceNode, SinkNode, NormalNode
	};

	am_addr_t sink_id = AM_BROADCAST_ADDR;

	distance_neighbours_t neighbours;

	SequenceNumber away_sequence_counter;
	SequenceNumber fake_sequence_counter;

	SequenceNumber source_fake_sequence_counter;
	uint32_t source_fake_sequence_increments;

	int16_t min_source_distance = BOTTOM;
	int16_t sink_distance = BOTTOM;

	bool sink_received_away_reponse = FALSE;

	bool first_normal_rcvd = FALSE;

	unsigned int extra_to_send = 0;

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

	uint32_t get_away_delay(void)
	{
		//assert(SOURCE_PERIOD_MS != BOTTOM);

		return 75;
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

	double get_sources_Fake_receive_ratio(void)
	{
		// Need to add one here because it is possible for the values to both be 0
		// if no fake messages have ever been received.
		const uint32_t seq_inc = source_fake_sequence_increments + 1;
		const uint32_t counter = sequence_number_get(&source_fake_sequence_counter) + 1;

		return seq_inc / (double)counter;
	}

	uint32_t get_pfs_period(void)
	{
		const uint16_t est_num_sources = estimated_number_of_sources();

		const double fake_rcv_ratio_at_src = get_sources_Fake_receive_ratio();

		const double period_per_source = SOURCE_PERIOD_MS / est_num_sources;

		// Reducing by the fake receive ratio means more messages are sent when
		// the ratio is lower. This helps compensate for collisions and lost fake messages.
		const uint32_t result_period = (uint32_t)ceil(period_per_source * fake_rcv_ratio_at_src);

		simdbg("stdout", "get_pfs_period=%u fakercv=%f\n",
			result_period, fake_rcv_ratio_at_src);

		return result_period;
	}

	uint32_t beacon_send_wait(void)
	{
		return 75U + (uint32_t)(50U * random_float());
	}

	uint32_t dummy_normal_send_wait(void)
	{
		if (sink_distance == BOTTOM)
		{
			return 25U + (uint32_t)(50U * random_float());
		}
		else
		{
			return 25U + (3 * 6 * sink_distance);
		}
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

	bool is_neighbour_closer_to_source(am_addr_t address)
	{
		size_t i;

		// Can't find node further from the source if we do not know our source distance
		if (min_source_distance != BOTTOM)
		{
			for (i = 0; i != neighbours.size; ++i)
			{
				distance_neighbour_detail_t const* const neighbour = &neighbours.data[i];

				if (neighbour->address != address)
				{
					continue;
				}

				if (neighbour->contents.min_source_distance == BOTTOM)
				{
					continue;
				}

				// If this neighbours closest source is further than our closest source,
				// then we want to consider them for the next fake source.
				return neighbour->contents.min_source_distance < min_source_distance;
			}
		}

		return FALSE;
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

	void update_neighbours_dummy_normal(const DummyNormalMessage* rcvd, am_addr_t source_addr)
	{
		distance_container_t dist;
		dist.min_source_distance = rcvd->sender_min_source_distance;
		insert_distance_neighbour(&neighbours, source_addr, &dist);
	}

	void update_source_distance(const NormalMessage* rcvd)
	{
		const uint16_t* distance = call SourceDistances.get(rcvd->source_id);
		const uint16_t* sink_source_distance = call SinkSourceDistances.get(rcvd->source_id);

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

			call BeaconSenderTimer.startOneShot(beacon_send_wait());
		}
		
		if (rcvd->sink_distance != BOTTOM)
		{
			if (sink_source_distance == NULL)
			{
				//simdbg("stdout", "Updating sink distance of %u to %d\n", rcvd->source_id, rcvd->sink_distance);
				call SinkSourceDistances.put(rcvd->source_id, rcvd->sink_distance);
			}
			else
			{
				call SinkSourceDistances.put(rcvd->source_id, min(*sink_source_distance, rcvd->sink_distance));
			}
		}
	}

	void update_sink_distance(const AwayMessage* rcvd, am_addr_t source_addr)
	{
		sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);
	}

	void update_fake_seq_incs(const NormalMessage* rcvd)
	{
		if (sequence_number_before(&source_fake_sequence_counter, rcvd->fake_sequence_number))
		{
			source_fake_sequence_counter = rcvd->fake_sequence_number;
			source_fake_sequence_increments = rcvd->fake_sequence_increments;
		}
	}


	bool busy = FALSE;
	message_t packet;

	event void Boot.booted()
	{
		sequence_number_init(&away_sequence_counter);
		sequence_number_init(&fake_sequence_counter);

		source_fake_sequence_increments = 0;
		sequence_number_init(&source_fake_sequence_counter);

		call MessageType.register_pair(NORMAL_CHANNEL, "Normal");
        call MessageType.register_pair(AWAY_CHANNEL, "Away");
        call MessageType.register_pair(FAKE_CHANNEL, "Fake");
        call MessageType.register_pair(BEACON_CHANNEL, "Beacon");
        call MessageType.register_pair(DUMMY_NORMAL_CHANNEL, "DummyNormal");

		call NodeType.register_pair(SourceNode, "SourceNode");
		call NodeType.register_pair(SinkNode, "SinkNode");
		call NodeType.register_pair(NormalNode, "NormalNode");

		if (call NodeType.is_node_sink())
		{
			AwayMessage message;
			call FakeMessageGenerator.start(&message, sizeof(message));

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

			call SourceDistances.put(TOS_NODE_ID, 0);

			call BroadcastNormalTimer.startPeriodic(SOURCE_PERIOD_MS);
		}
	}

	event void ObjectDetector.stoppedDetecting()
	{
		if (call NodeType.get() == SourceNode)
		{
			call BroadcastNormalTimer.stop();

			call SourceDistances.remove(TOS_NODE_ID);

			call NodeType.set(NormalNode);
		}
	}

	USE_MESSAGE(Normal);
	USE_MESSAGE(Away);
	USE_MESSAGE(Fake);
	USE_MESSAGE(DummyNormal);
	USE_MESSAGE(Beacon);

	event void BroadcastNormalTimer.fired()
	{
		NormalMessage message;

		simdbgverbose("SourceBroadcasterC", "BroadcastNormalTimer fired.\n");

		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;
		message.sink_distance = sink_distance;

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

		sequence_number_increment(&away_sequence_counter);

		extra_to_send = 2;
		send_Away_message(&message, AM_BROADCAST_ADDR);
	}

	event void BeaconSenderTimer.fired()
	{
		BeaconMessage message;
		bool result;

		simdbgverbose("stdout", "BeaconSenderTimer fired.\n");

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

	event void DummyNormalSenderTimer.fired()
	{
		DummyNormalMessage message;
		bool result;

		simdbgverbose("stdout", "DummyNormalSenderTimer fired.\n");

		if (busy)
		{
			simdbgverbose("stdout", "Device is busy rescheduling DummyNormal\n");
			call DummyNormalSenderTimer.startOneShot(dummy_normal_send_wait());
			return;
		}

		message.sender_min_source_distance = min_source_distance;

		message.sender_sink_distance = sink_distance;

		result = send_DummyNormal_message(&message, AM_BROADCAST_ADDR);
		if (!result)
		{
			simdbgverbose("stdout", "Send failed rescheduling DummyNormal\n");
			call DummyNormalSenderTimer.startOneShot(dummy_normal_send_wait());
			return;
		}
	}


	void x_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		update_fake_seq_incs(rcvd);

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
			}

			forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;
			forwarding_message.fake_sequence_number = source_fake_sequence_counter;
			forwarding_message.fake_sequence_increments = source_fake_sequence_increments;

			send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);

			if (is_neighbour_closer_to_source(source_addr))
			{
				call DummyNormalSenderTimer.startOneShot(dummy_normal_send_wait());
			}
		}
	}

	void Sink_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		update_fake_seq_incs(rcvd);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			update_source_distance(rcvd);

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

			if (is_neighbour_closer_to_source(source_addr))
			{
				call DummyNormalSenderTimer.startOneShot(dummy_normal_send_wait());
			}	
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SinkNode: Sink_receive_Normal(rcvd, source_addr); break;
		case NormalNode: x_receive_Normal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)


	void Sink_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		sink_received_away_reponse = TRUE;

		call BeaconSenderTimer.startOneShot(beacon_send_wait());
	}

	void Source_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		sink_id = rcvd->source_id;

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			update_sink_distance(rcvd, source_addr);

			forwarding_message = *rcvd;
			forwarding_message.sink_distance += 1;

			extra_to_send = 1;
			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);

			call BeaconSenderTimer.startOneShot(beacon_send_wait());
		}
	}

	void Normal_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		sink_id = rcvd->source_id;

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			update_sink_distance(rcvd, source_addr);


			forwarding_message = *rcvd;
			forwarding_message.sink_distance += 1;

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
			source_fake_sequence_increments += 1;

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

			if (!is_neighbour_closer_to_source(source_addr))
			{
				send_Fake_message(&forwarding_message, AM_BROADCAST_ADDR);
			}
			else
			{
				call DummyNormalSenderTimer.startOneShot(dummy_normal_send_wait());
			}
		}
	}

	RECEIVE_MESSAGE_BEGIN(Fake, Receive)
		case SinkNode: Sink_receive_Fake(rcvd, source_addr); break;
		case SourceNode: Source_receive_Fake(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Fake(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Fake)



	void x_receive_DummyNormal(const DummyNormalMessage* const rcvd, am_addr_t source_addr)
	{
		update_neighbours_dummy_normal(rcvd, source_addr);

		METRIC_RCV_DUMMYNORMAL(rcvd);

		sink_distance = minbot(sink_distance, botinc(rcvd->sender_sink_distance));
	}

	RECEIVE_MESSAGE_BEGIN(DummyNormal, Receive)
		case SinkNode:
		case SourceNode:
		case NormalNode: x_receive_DummyNormal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(DummyNormal)



	void x_receive_Beacon(const BeaconMessage* const rcvd, am_addr_t source_addr)
	{
		update_neighbours_beacon(rcvd, source_addr);

		METRIC_RCV_BEACON(rcvd);

		sink_distance = minbot(sink_distance, botinc(rcvd->sink_distance));
	}

	RECEIVE_MESSAGE_BEGIN(Beacon, Receive)
		case SinkNode:
		case SourceNode:
		case NormalNode: x_receive_Beacon(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Beacon)


	event uint32_t FakeMessageGenerator.initialStartDelay()
	{
		return signal FakeMessageGenerator.calculatePeriod() / 2;
	}

	event uint32_t FakeMessageGenerator.calculatePeriod()
	{
		return get_pfs_period();
	}

	event void FakeMessageGenerator.sendFakeMessage()
	{
		FakeMessage message;

		message.sequence_number = sequence_number_next(&fake_sequence_counter);
		message.sender_sink_distance = sink_distance;
		message.message_type = call NodeType.get();
		message.source_id = TOS_NODE_ID;
		message.sender_min_source_distance = min_source_distance;

		if (send_Fake_message(&message, AM_BROADCAST_ADDR))
		{
			sequence_number_increment(&fake_sequence_counter);
		}
	}

	event void FakeMessageGenerator.durationExpired(const void* original, uint8_t original_size)
	{
		// Duration should never expire
		assert(FALSE);
	}
}
