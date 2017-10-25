#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"
#include "NeighbourDetail.h"

#include "AwayMessage.h"
#include "DummyNormalMessage.h"
#include "NormalMessage.h"
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

	uses interface AMSend as DummyNormalSend;
	uses interface Receive as DummyNormalReceive;

	uses interface AMSend as BeaconSend;
	uses interface Receive as BeaconReceive;

	uses interface MetricLogging;
	uses interface MetricHelpers;

	uses interface NodeType;
	uses interface MessageType;
	uses interface ObjectDetector;

	uses interface SequenceNumbers as NormalSeqNos;
}

implementation
{
	enum
	{
		SourceNode, SinkNode, NormalNode
	};

	distance_neighbours_t neighbours;

	SequenceNumber away_sequence_counter;

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

	uint32_t beacon_send_wait(void)
	{
		return 75U + (uint32_t)(50U * random_float());
	}

	uint32_t dummy_normal_send_wait(void)
	{
		if (sink_distance != BOTTOM)
		{
			return 25U + sink_distance * 3;
		}
		else
		{
			return 25U + (uint32_t)(50U * random_float());
		}
	}

	void find_neighbours_further_or_same_from_source(distance_neighbours_t* local_neighbours)
	{
		size_t i;

		init_distance_neighbours(local_neighbours);

		// Can't find node further from the source if we do not know our source distance
		if (min_source_distance != BOTTOM)
		{
			for (i = 0; i != neighbours.size; ++i)
			{
				distance_neighbour_detail_t const* const neighbour = &neighbours.data[i];

				// If this neighbours closest source is further than our closest source,
				// then we want to consider them for the next fake source.
				if (neighbour->contents.min_source_distance >= min_source_distance)
				{
					insert_distance_neighbour(local_neighbours, neighbour->address, &neighbour->contents);
				}
			}
		}
	}

	bool is_neighbour_further_or_same_from_source(am_addr_t address)
	{
		uint16_t i, end; 

		distance_neighbours_t local_neighbours;
		find_neighbours_further_or_same_from_source(&local_neighbours);

		for (i = 0, end = local_neighbours.size; i != end; ++i)
		{
			if (local_neighbours.data[i].address == address)
				return TRUE;
		}

		return FALSE;
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
		if (min_source_distance == BOTTOM || min_source_distance > rcvd->source_distance + 1)
		{
			min_source_distance = rcvd->source_distance + 1;

			call BeaconSenderTimer.startOneShot(beacon_send_wait());
		}
	}

	void update_sink_distance(const AwayMessage* rcvd, am_addr_t source_addr)
	{
		sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);
	}


	bool busy = FALSE;
	message_t packet;

	event void Boot.booted()
	{
		METRIC_BOOT();

		sequence_number_init(&away_sequence_counter);

		call MessageType.register_pair(NORMAL_CHANNEL, "Normal");
		call MessageType.register_pair(AWAY_CHANNEL, "Away");
		call MessageType.register_pair(DUMMY_NORMAL_CHANNEL, "DummyNormal");
		call MessageType.register_pair(BEACON_CHANNEL, "Beacon");

		call NodeType.register_pair(SourceNode, "SourceNode");
		call NodeType.register_pair(SinkNode, "SinkNode");
		call NodeType.register_pair(NormalNode, "NormalNode");

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

	USE_MESSAGE(Normal);
	USE_MESSAGE(Away);
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

		message.flood_limit = 2;

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

			send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);

			if (!is_neighbour_further_or_same_from_source(source_addr))
			{
				call DummyNormalSenderTimer.startOneShot(dummy_normal_send_wait());
			}
		}
	}

	void Sink_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
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


	void x_receive_DummyNormal(const DummyNormalMessage* const rcvd, am_addr_t source_addr)
	{
		update_neighbours_dummy_normal(rcvd, source_addr);

		METRIC_RCV_DUMMYNORMAL(rcvd);

		sink_distance = minbot(sink_distance, botinc(rcvd->sender_sink_distance));

		// NOTE: This is broken as nodes that originally sent this message
		// will send it for a second time when they receive it again
		if (rcvd->flood_limit > 1)
		{
			DummyNormalMessage forwarding_message = *rcvd;
			forwarding_message.flood_limit -= 1;

			send_DummyNormal_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
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
}
