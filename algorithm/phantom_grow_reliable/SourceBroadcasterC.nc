#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"
#include "NeighbourDetail.h"

#include "bloom_filter.h"
#include "bloom_filter.c"

#include "NormalMessage.h"
#include "AwayMessage.h"
#include "BeaconMessage.h"

#include <Timer.h>
#include <TinyError.h>

#include <assert.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, msg->sink_distance + 1)
#define METRIC_RCV_BEACON(msg) METRIC_RCV(Beacon, source_addr, BOTTOM, BOTTOM, BOTTOM)

typedef struct
{
	int16_t sink_distance;
} sink_distance_container_t;

void dsink_update(sink_distance_container_t* find, sink_distance_container_t const* given)
{
	find->sink_distance = minbot(find->sink_distance, given->sink_distance);
}

void dsink_print(char* name, size_t i, am_addr_t address, sink_distance_container_t const* contents)
{
	dbg_clear(name, "[%u] => addr=%u / dsink=%d",
		i, address, contents->sink_distance);
}

DEFINE_NEIGHBOUR_DETAIL(sink_distance_container_t, dsink, dsink_update, dsink_print, 16);

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;

	uses interface Timer<TMilli> as BroadcastNormalTimer;
	uses interface Timer<TMilli> as AwaySenderTimer;
	uses interface Timer<TMilli> as BeaconSenderTimer;

	uses interface Packet;
	uses interface AMPacket;
	uses interface PacketLink;
	uses interface PacketAcknowledgements;

	uses interface SplitControl as RadioControl;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;
	uses interface Receive as NormalSnoop;

	uses interface AMSend as AwaySend;
	uses interface Receive as AwayReceive;

	uses interface AMSend as BeaconSend;
	uses interface Receive as BeaconReceive;

	uses interface SourcePeriodModel;
	uses interface ObjectDetector;

	uses interface SequenceNumbers as NormalSeqNos;
	uses interface SequenceNumbers as SnoopedNormalSeqNos;
	uses interface SequenceNumbers as AwaySeqNos;

	uses interface Dictionary<am_addr_t, int32_t> as SnoopedNormalSeqNosSrcDist;
	 
	uses interface Random;
}

implementation 
{
	typedef enum
	{
		SourceNode, SinkNode, NormalNode
	} NodeType;

	NodeType type = NormalNode;

	typedef enum
	{
		UnknownSet = 0, CloserSet = (1 << 0), FurtherSet = (1 << 1)
	} SetType;

	const char* type_to_string()
	{
		switch (type)
		{
		case SourceNode:      return "SourceNode";
		case SinkNode:        return "SinkNode  ";
		case NormalNode:      return "NormalNode";
		default:              return "<unknown> ";
		}
	}

	int16_t sink_distance = BOTTOM;

	dsink_neighbours_t neighbours;

	bool busy = FALSE;
	message_t packet;

	uint32_t extra_to_send = 0;

	bloom_filter_t current_bloom_filter;
	uint8_t unicast_retries = 0;

	uint32_t get_source_period()
	{
		assert(type == SourceNode);
		return call SourcePeriodModel.get();
	}

	uint16_t random_walk_retries()
	{
		return RANDOM_WALK_RETRIES;
	}

	uint16_t random_walk_delay(uint32_t source_period)
	{
		return random_walk_retries() / source_period;
	}

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

	am_addr_t random_walk_target(NormalMessage const* rcvd, const nx_bloom_filter_t* bloom, const am_addr_t* to_ignore, size_t to_ignore_length)
	{
		am_addr_t chosen_address;
		uint32_t i;

		dsink_neighbours_t local_neighbours;
		init_dsink_neighbours(&local_neighbours);

		for (i = 0; i != neighbours.size; ++i)
		{
			dsink_neighbour_detail_t const* const neighbour = &neighbours.data[i];

			// Skip neighbours we have been asked to
			if (to_ignore != NULL)
			{
				size_t j;
				bool found = FALSE;
				for (j = 0; j != to_ignore_length; ++j)
				{
					if (to_ignore[j] == neighbour->address)
					{
						found = TRUE;
						break;
					}
				}
				if (found)
				{
					dbgverbose("slp-debug", "Ignoring %u as we have been asked to\n", neighbour->address);
					continue;
				}
			}

			// Skip neighbours that are neighbours of the previous node
			if (bloom != NULL && bloom_filter_test(bloom, neighbour->address))
			{
				dbgverbose("slp-debug", "Dropping the node %u as it is in the bloom filter\n", neighbour->address);
				continue;
			}

			insert_dsink_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
		}

		if (local_neighbours.size == 0)
		{
			dbgverbose("slp-debug", "No local neighbours to choose so broadcasting. (my-dsink=%d, my-neighbours-size=%u)\n",
				sink_distance, neighbours.size);

			chosen_address = AM_BROADCAST_ADDR;
		}
		else
		{
			// Choose a neighbour with equal probabilities.
			const uint16_t rnd = call Random.rand16();
			const uint16_t neighbour_index = rnd % local_neighbours.size;
			const dsink_neighbour_detail_t* const neighbour = &local_neighbours.data[neighbour_index];

			chosen_address = neighbour->address;

#ifdef SLP_VERBOSE_DEBUG
			print_dsink_neighbours("stdout", &local_neighbours);
#endif

			dbgverbose("stdout", "Chosen %u at index %u (rnd=%u) out of %u neighbours (their-dsink=%d my-dsink=%d)\n",
				chosen_address, neighbour_index, rnd, local_neighbours.size,
				neighbour->contents.sink_distance, sink_distance);
		}

		return chosen_address;
	}

	uint32_t beacon_send_wait()
	{
		return 75U + (uint32_t)(50U * random_float());
	}

	USE_MESSAGE_WITH_CALLBACK(Normal);
	USE_MESSAGE(Away);
	USE_MESSAGE(Beacon);

	void send_Normal_done(message_t* msg, error_t error)
	{
		const NormalMessage* const message = call Packet.getPayload(msg, sizeof(NormalMessage));
		am_addr_t previous_target;
		am_addr_t target;

		if (unicast_retries > 2)
		{
			return;
		}

		if (call PacketLink.getRetries(msg) <= 0)
		{
			return;
		}

		// If the message wasn't delivered and we are unicasting,
		// then try and find another target to send to.
		if (call PacketLink.wasDelivered(msg))
		{
			//dbg("slp-debug", "Dropping message %u as it has been delivered.\n",
			//	message->sequence_number);
			return;
		}

		// We have snooped this message from a node further from the source, so give up trying to forward it.
		if (!call SnoopedNormalSeqNos.before(message->source_id, message->sequence_number) &&
			*call SnoopedNormalSeqNosSrcDist.get(message->source_id) > message->source_distance)
		{
			//dbg("slp-debug", "Dropping message as we have snooped a further message (dist %u > %u).\n",
			//	*call SnoopedNormalSeqNosSrcDist.get(message->source_id), message->source_distance);
			return;
		}

		previous_target = call AMPacket.destination(msg);

		// Get a target, ignoring the previous target
		// TODO: really the sender of this message should also be ignored.
		target = random_walk_target(message, &current_bloom_filter, &previous_target, 1);

		// Can't decide on a target, then give up.
		if (target != AM_BROADCAST_ADDR)
		{
			++unicast_retries;

			dbgverbose("stdout", "%s: Forwarding normal from %u to target = %u. THIS IS A NTH ATTEMPT AT A UNICAST!!!!!!!!\n",
				sim_time_string(), TOS_NODE_ID, target);

			call PacketLink.setRetries(msg, random_walk_retries());
			call PacketLink.setRetryDelay(msg, random_walk_delay(message->source_period));
			call PacketAcknowledgements.noAck(msg);

			send_Normal_message(message, target);
		}
	}

	event void Boot.booted()
	{
		dbgverbose("Boot", "%s: Application booted.\n", sim_time_string());

		init_dsink_neighbours(&neighbours);

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

			if (type == SinkNode)
			{
				call AwaySenderTimer.startOneShot(1 * 1000); // One second
			}
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

	void fill_bloom_neighbours(nx_bloom_filter_t* bloom)
	{
		uint32_t i;

		bloom_filter_clear(bloom);

		// Find nodes whose sink distance is less than or greater than
		// our sink distance.
		for (i = 0; i != neighbours.size; ++i)
		{
			bloom_filter_add(bloom, neighbours.data[i].address);
		}

		/*for (i = 0; i != neighbours.size; ++i)
		{
			assert(bloom_filter_test(bloom, neighbours.data[i].address));
		}*/
	}


	event void BroadcastNormalTimer.fired()
	{
		NormalMessage message;
		am_addr_t target;

		const uint32_t source_period = get_source_period();

		dbgverbose("SourceBroadcasterC", "%s: BroadcastNormalTimer fired.\n", sim_time_string());

#ifdef SLP_VERBOSE_DEBUG
		print_dsink_neighbours("stdout", &neighbours);
#endif

		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;
		message.sink_distance_of_sender = sink_distance;
		message.source_period = source_period;

		memset(&current_bloom_filter, 0, sizeof(current_bloom_filter));
		fill_bloom_neighbours(&message.senders_neighbours);

		target = random_walk_target(&message, NULL, NULL, 0);

		dbgverbose("stdout", "%s: Forwarding normal from source to target = %u in direction %u\n",
			sim_time_string(), target, message.further_or_closer_set);

		call Packet.clear(&packet);
		call PacketLink.setRetries(&packet, random_walk_retries());
		call PacketLink.setRetryDelay(&packet, random_walk_delay(source_period));
		call PacketAcknowledgements.noAck(&packet);

		unicast_retries = 0;

		if (send_Normal_message(&message, target))
		{
			call NormalSeqNos.increment(TOS_NODE_ID);
		}

		call BroadcastNormalTimer.startOneShot(source_period);
	}

	event void AwaySenderTimer.fired()
	{
		AwayMessage message;

		dbgverbose("SourceBroadcasterC", "%s: AwaySenderTimer fired.\n", sim_time_string());

		sink_distance = 0;

		message.sequence_number = call AwaySeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.sink_distance = sink_distance;

		call Packet.clear(&packet);
		call PacketLink.setRetries(&packet, 0);
		call PacketLink.setRetryDelay(&packet, 0);
		call PacketAcknowledgements.noAck(&packet);

		extra_to_send = 2;
		if (send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			call AwaySeqNos.increment(TOS_NODE_ID);
		}

		dbgverbose("stdout", "Away sent\n");
	}

	event void BeaconSenderTimer.fired()
	{
		BeaconMessage message;

		dbgverbose("SourceBroadcasterC", "%s: BeaconSenderTimer fired.\n", sim_time_string());

		message.sink_distance_of_sender = sink_distance;

		call Packet.clear(&packet);
		call PacketLink.setRetries(&packet, 0);
		call PacketLink.setRetryDelay(&packet, 0);
		call PacketAcknowledgements.noAck(&packet);

		send_Beacon_message(&message, AM_BROADCAST_ADDR);
	}

	void process_normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		const sink_distance_container_t dsink = { rcvd->sink_distance_of_sender };
		insert_dsink_neighbour(&neighbours, source_addr, &dsink);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;
			forwarding_message.sink_distance_of_sender = sink_distance;

			current_bloom_filter = rcvd->senders_neighbours;
			fill_bloom_neighbours(&forwarding_message.senders_neighbours);

			if (rcvd->source_distance + 1 < RANDOM_WALK_HOPS && !rcvd->forced_broadcast)
			{
				am_addr_t target;

				// Get a target, ignoring the node that sent us this message
				target = random_walk_target(&forwarding_message, &rcvd->senders_neighbours, &source_addr, 1);

				// If we can't decide on a target, then give up.
				if (target == AM_BROADCAST_ADDR)
				{
					forwarding_message.forced_broadcast = TRUE;
				}

				dbgverbose("stdout", "%s: Forwarding normal from %u to target = %u\n",
					sim_time_string(), TOS_NODE_ID, target);

				unicast_retries = 0;

				call Packet.clear(&packet);
				call PacketLink.setRetries(&packet, random_walk_retries());
				call PacketLink.setRetryDelay(&packet, random_walk_delay(rcvd->source_period));
				call PacketAcknowledgements.noAck(&packet);

				send_Normal_message(&forwarding_message, target);
			}
			else
			{
				if (rcvd->source_distance + 1 == RANDOM_WALK_HOPS && !rcvd->forced_broadcast)
				{
					dbg_clear("Metric-PATH-END", SIM_TIME_SPEC ",%u,%u,%u," SEQUENCE_NUMBER_SPEC ",%u\n",
						sim_time(), TOS_NODE_ID, source_addr,
						rcvd->source_id, rcvd->sequence_number, rcvd->source_distance + 1);
				}

				call Packet.clear(&packet);
				call PacketLink.setRetries(&packet, 0);
				call PacketLink.setRetryDelay(&packet, 0);
				call PacketAcknowledgements.noAck(&packet);

				send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
			}
		}
	}

	void Normal_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (rcvd->sink_distance_of_sender != BOTTOM)
			sink_distance = minbot(sink_distance, rcvd->sink_distance_of_sender + 1);

		process_normal(msg, rcvd, source_addr);
	}

	void Sink_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		// It is helpful to have the sink forward Normal messages onwards
		// Otherwise there is a chance the random walk would terminate at the sink and
		// not flood the network.
		process_normal(msg, rcvd, source_addr);
	}

	void Source_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		const sink_distance_container_t dsink = { rcvd->sink_distance_of_sender };
		insert_dsink_neighbour(&neighbours, source_addr, &dsink);

		if (rcvd->sink_distance_of_sender != BOTTOM)
			sink_distance = minbot(sink_distance, rcvd->sink_distance_of_sender + 1);
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SourceNode: Source_receieve_Normal(msg, rcvd, source_addr); break;
		case SinkNode: Sink_receieve_Normal(msg, rcvd, source_addr); break;
		case NormalNode: Normal_receieve_Normal(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)

	// If the sink snoops a normal message, we may as well just deliver it
	void Sink_snoop_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		const sink_distance_container_t dsink = { rcvd->sink_distance_of_sender };
		insert_dsink_neighbour(&neighbours, source_addr, &dsink);

		if (call SnoopedNormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call SnoopedNormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);
			call SnoopedNormalSeqNosSrcDist.put(rcvd->source_id, rcvd->source_distance + 1);
		}

		// TODO: Enable this when the sink can snoop and then correctly
		// respond to a message being received.
		/*if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			dbgverbose("stdout", "%s: Received unseen Normal by snooping seqno=%u from %u (dsrc=%u).\n",
				sim_time_string(), rcvd->sequence_number, source_addr, rcvd->source_distance + 1);
		}*/
	}

	void x_snoop_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		const sink_distance_container_t dsink = { rcvd->sink_distance_of_sender };
		insert_dsink_neighbour(&neighbours, source_addr, &dsink);

		if (rcvd->sink_distance_of_sender != BOTTOM)
		{
			sink_distance = minbot(sink_distance, rcvd->sink_distance_of_sender + 1);
		}

		if (call SnoopedNormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call SnoopedNormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);
			call SnoopedNormalSeqNosSrcDist.put(rcvd->source_id, rcvd->source_distance + 1);
		}

		//dbgverbose("stdout", "Snooped a normal from %u intended for %u (rcvd-dsink=%d, my-dsink=%d)\n",
		//  source_addr, call AMPacket.destination(msg), rcvd->sink_distance_of_sender, sink_distance);
	}

	// We need to snoop packets that may be unicasted,
	// so the attacker properly responds to them.
	RECEIVE_MESSAGE_BEGIN(Normal, Snoop)
		case SourceNode: x_snoop_Normal(msg, rcvd, source_addr); break;
		case SinkNode: Sink_snoop_Normal(msg, rcvd, source_addr); break;
		case NormalNode: x_snoop_Normal(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)


	void x_receieve_Away(message_t* msg, const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		const sink_distance_container_t dsink = { rcvd->sink_distance };
		insert_dsink_neighbour(&neighbours, source_addr, &dsink);

		sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);

		if (call AwaySeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			call AwaySeqNos.update(rcvd->source_id, rcvd->sequence_number);
			
			METRIC_RCV_AWAY(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.sink_distance += 1;

			call Packet.clear(&packet);
			call PacketLink.setRetries(&packet, 0);
			call PacketLink.setRetryDelay(&packet, 0);
			call PacketAcknowledgements.noAck(&packet);

			extra_to_send = 1;
			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);

			call BeaconSenderTimer.startOneShot(beacon_send_wait());
		}

#ifdef SLP_VERBOSE_DEBUG
		print_dsink_neighbours("stdout", &neighbours);
#endif
	}

	RECEIVE_MESSAGE_BEGIN(Away, Receive)
		case NormalNode: x_receieve_Away(msg, rcvd, source_addr); break;
		case SourceNode: x_receieve_Away(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Away)


	void x_receieve_Beacon(message_t* msg, const BeaconMessage* const rcvd, am_addr_t source_addr)
	{
		const sink_distance_container_t dsink = { rcvd->sink_distance_of_sender };
		insert_dsink_neighbour(&neighbours, source_addr, &dsink);

		if (rcvd->sink_distance_of_sender != BOTTOM)
			sink_distance = minbot(sink_distance, rcvd->sink_distance_of_sender + 1);

		METRIC_RCV_BEACON(rcvd);
	}

	RECEIVE_MESSAGE_BEGIN(Beacon, Receive)
		case NormalNode: x_receieve_Beacon(msg, rcvd, source_addr); break;
		case SourceNode: x_receieve_Beacon(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Beacon)
}
