#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "NormalMessage.h"
#include "AwayMessage.h"
#include "BeaconMessage.h"

#include <Timer.h>
#include <TinyError.h>

#include <assert.h>

#define METRIC_RCV(TYPE, DISTANCE) \
	dbg_clear("Metric-RCV", "%s,%" PRIu64 ",%u,%u,%u,%u\n", #TYPE, sim_time(), TOS_NODE_ID, source_addr, rcvd->sequence_number, DISTANCE)

#define METRIC_BCAST(TYPE, STATUS) \
	dbg_clear("Metric-BCAST", "%s,%" PRIu64 ",%u,%s,%u\n", #TYPE, sim_time(), TOS_NODE_ID, STATUS, (tosend != NULL) ? tosend->sequence_number : (uint32_t)-1)


typedef struct
{
	am_addr_t address;
	int16_t sink_distance;
} NeighbourDetail;

// The maximum size of the 2-hop neighbourhood,
// When the 1-hop neighbourhood has a maximum size of 4 nodes.
enum { MaxNeighbours = 16 };

typedef struct
{
	NeighbourDetail data[MaxNeighbours];
	uint32_t size;
} Neighbours;

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

	uses interface AMSend as AwaySend;
	uses interface Receive as AwayReceive;

	uses interface AMSend as BeaconSend;
	uses interface Receive as BeaconReceive;

	uses interface SourcePeriodModel;
	uses interface ObjectDetector;
	 
	uses interface Random;
}

implementation 
{
	inline void init_neighbours(Neighbours* neighbours)
	{
		neighbours->size = 0;
	}

	NeighbourDetail* find_neighbour(Neighbours* neighbours, am_addr_t address)
	{
		uint32_t i;
		for (i = 0; i != neighbours->size; ++i)
		{
			if (neighbours->data[i].address == address)
			{
				return &neighbours->data[i];
			}
		}
		return NULL;
	}

	bool insert_neighbour(Neighbours* neighbours, am_addr_t address, int16_t sink_distance)
	{
		NeighbourDetail* find = find_neighbour(neighbours, address);

		if (find != NULL)
		{
			find->sink_distance = minbot(find->sink_distance, sink_distance);
		}
		else
		{
			if (neighbours->size < MaxNeighbours)
			{
				find = &neighbours->data[neighbours->size];

				find->address = address;
				find->sink_distance = sink_distance;

				neighbours->size += 1;
			}
		}

		return find != NULL;
	}

	void print_neighbours(char* name, Neighbours const* neighbours)
	{
#ifdef TOSSIM
		uint32_t i;
		dbg(name, "Neighbours(size=%d, values=", neighbours->size);
		for (i = 0; i != neighbours->size; ++i)
		{
			NeighbourDetail const* neighbour = &neighbours->data[i];
			dbg_clear(name, "[%u] => %u / %d",
				i, neighbour->address, neighbour->sink_distance);

			if ((i + 1) != neighbours->size)
			{
				dbg_clear(name, ", ");
			}
		}
		dbg_clear(name, ")\n");
#endif
	}

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

	SequenceNumber normal_sequence_counter;
	SequenceNumber away_sequence_counter;

	int16_t sink_distance = BOTTOM;

	Neighbours neighbours;

	bool busy = FALSE;
	message_t packet;

	uint32_t extra_to_send = 0;

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

	SetType random_walk_direction()
	{
		uint32_t i;
		uint32_t possible_sets = 0;

		//assert(type == SourceNode);

		if (sink_distance != BOTTOM)
		{
			for (i = 0; i != neighbours.size; ++i)
			{
				NeighbourDetail const* const neighbour = &neighbours.data[i];

				if (sink_distance < neighbour->sink_distance)
				{
					possible_sets |= FurtherSet;
				}
				else if (sink_distance > neighbour->sink_distance)
				{
					possible_sets |= CloserSet;
				}
			}
		}

		if (possible_sets == (FurtherSet | CloserSet))
		{
			// Both directions possible, so randomly pick one of them
			const uint16_t rnd = call Random.rand16() % 2;
			if (rnd == 0)
			{
				return FurtherSet;
			}
			else
			{
				return CloserSet;
			}
		}
		else if ((possible_sets & FurtherSet) != 0)
		{
			return FurtherSet;
		}
		else if ((possible_sets & CloserSet) != 0)
		{
			return CloserSet;
		}
		else
		{
			if (neighbours.size > 0)
			{
				// There are neighbours, but none with sensible distances...
				// Or we don't know our sink distance
				const uint16_t rnd = call Random.rand16() % 2;
				if (rnd == 0)
				{
					return FurtherSet;
				}
				else
				{
					return CloserSet;
				}
			}
			else
			{
				// No known neighbour, so have a go at flooding.
				// Someone might get this message
				return UnknownSet;
			}
		}
	}

	am_addr_t random_walk_target(NormalMessage const* rcvd, const am_addr_t* to_ignore)
	{
		am_addr_t chosen_address = AM_BROADCAST_ADDR;
		uint32_t i;

		Neighbours local_neighbours;
		init_neighbours(&local_neighbours);

		// If we don't know our sink distance then we cannot work
		// out which neighbour is in closer or further.
		if (sink_distance != BOTTOM)
		{
			for (i = 0; i != neighbours.size; ++i)
			{
				NeighbourDetail const* const neighbour = &neighbours.data[i];

				// Skip neighbours we have been asked to
				if (to_ignore != NULL && *to_ignore == neighbour->address)
				{
					continue;
				}

				//dbgverbose("stdout", "[%u]: further_or_closer_set=%d, dsink=%d neighbour.dsink=%d \n",
				//	neighbour->address, rcvd->further_or_closer_set, sink_distance, neighbour->sink_distance);

				if ((rcvd->further_or_closer_set == FurtherSet && sink_distance <= neighbour->sink_distance) ||
					(rcvd->further_or_closer_set == CloserSet && sink_distance >= neighbour->sink_distance))
				{
					insert_neighbour(&local_neighbours, neighbour->address, neighbour->sink_distance);
				}
			}
		}

		if (local_neighbours.size == 0)
		{
			//dbgverbose("stdout", "dsink=%d neighbours-size=%u \n", sink_distance, neighbours.size);

			chosen_address = AM_BROADCAST_ADDR;
		}
		else
		{
			// Choose a neighbour with equal probabilities.
			const uint16_t rnd = call Random.rand16();
			const uint16_t neighbour_index = rnd % local_neighbours.size;

#ifdef SLP_VERBOSE_DEBUG
			print_neighbours("stdout", &local_neighbours);
#endif

			chosen_address = local_neighbours.data[neighbour_index].address;

			dbgverbose("stdout", "Chosen %u at index %u (%u) out of %u neighbours\n", chosen_address, neighbour_index, rnd, local_neighbours.size);
		}

		return chosen_address;
	}

	uint32_t beacon_send_wait()
	{
		return 75U + (uint32_t)(50U * random_float());
	}


	USE_MESSAGE(Normal);
	USE_MESSAGE(Away);
	USE_MESSAGE(Beacon);
	

	event void Boot.booted()
	{
		dbgverbose("Boot", "%s: Application booted.\n", sim_time_string());

		sequence_number_init(&normal_sequence_counter);
		sequence_number_init(&away_sequence_counter);

		init_neighbours(&neighbours);

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


	event void BroadcastNormalTimer.fired()
	{
		NormalMessage message;
		am_addr_t target;

		const uint32_t source_period = get_source_period();

		dbgverbose("SourceBroadcasterC", "%s: BroadcastNormalTimer fired.\n", sim_time_string());

#ifdef SLP_VERBOSE_DEBUG
		print_neighbours("stdout", &neighbours);
#endif

		message.sequence_number = sequence_number_next(&normal_sequence_counter);
		message.source_distance = 0;
		message.sink_distance_of_sender = sink_distance;
		message.source_period = source_period;

		message.further_or_closer_set = random_walk_direction();

		target = random_walk_target(&message, NULL);

		dbgverbose("stdout", "%s: Forwarding normal from source to target = %u in direction %u\n",
			sim_time_string(), target, message.further_or_closer_set);

		call PacketLink.setRetries(&packet, random_walk_retries());
		call PacketLink.setRetryDelay(&packet, random_walk_delay(source_period));
		call PacketAcknowledgements.requestAck(&packet);

		if (send_Normal_message(&message, target))
		{
			sequence_number_increment(&normal_sequence_counter);
		}

		call BroadcastNormalTimer.startOneShot(source_period);
	}

	event void AwaySenderTimer.fired()
	{
		AwayMessage message;

		dbgverbose("SourceBroadcasterC", "%s: AwaySenderTimer fired.\n", sim_time_string());

		sink_distance = 0;

		message.sequence_number = sequence_number_next(&away_sequence_counter);
		message.sink_distance = sink_distance;

		call PacketLink.setRetries(&packet, 0);
		call PacketLink.setRetryDelay(&packet, 0);
		call PacketAcknowledgements.noAck(&packet);

		extra_to_send = 2;
		if (send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			sequence_number_increment(&away_sequence_counter);
		}

		dbgverbose("stdout", "Away sent\n");
	}

	event void BeaconSenderTimer.fired()
	{
		BeaconMessage message;

		dbgverbose("SourceBroadcasterC", "%s: BeaconSenderTimer fired.\n", sim_time_string());

		message.sequence_number = 0;
		message.sender_sink_distance = sink_distance;

		call PacketLink.setRetries(&packet, 0);
		call PacketLink.setRetryDelay(&packet, 0);
		call PacketAcknowledgements.noAck(&packet);

		send_Beacon_message(&message, AM_BROADCAST_ADDR);
	}

	void Normal_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		insert_neighbour(&neighbours, source_addr, rcvd->sink_distance_of_sender);

		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Normal, rcvd->source_distance + 1);

			dbgverbose("stdout", "%s: Received unseen Normal seqno=%u from %u (dsrc=%u).\n",
				sim_time_string(), rcvd->sequence_number, source_addr, rcvd->source_distance + 1);

			forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;
			forwarding_message.sink_distance_of_sender = sink_distance;

			if (rcvd->source_distance < RANDOM_WALK_HOPS)
			{
				am_addr_t target;

				// The previous node(s) were unable to choose a direction,
				// so lets try to
				if (forwarding_message.further_or_closer_set == UnknownSet)
				{
					forwarding_message.further_or_closer_set = random_walk_direction();

					dbgverbose("stdout", "%s: Unknown direction, setting to %d\n",
						sim_time_string(), forwarding_message.further_or_closer_set);
				}

				target = random_walk_target(&forwarding_message, &source_addr);

				dbgverbose("stdout", "%s: Forwarding normal from %u to target = %u\n",
					sim_time_string(), TOS_NODE_ID, target);

				call PacketLink.setRetries(&packet, random_walk_retries());
				call PacketLink.setRetryDelay(&packet, random_walk_delay(rcvd->source_period));
				call PacketAcknowledgements.requestAck(&packet);

				send_Normal_message(&forwarding_message, target);
			}
			else
			{
				call PacketLink.setRetries(&packet, 0);
				call PacketLink.setRetryDelay(&packet, 0);
				call PacketAcknowledgements.noAck(&packet);

				send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
			}
		}
	}

	void Sink_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		// It is helpful to have the sink forward Normal messages onwards
		// Otherwise there is a chance the random walk would terminate at the sink and
		// not flood the network.
		Normal_receieve_Normal(msg, rcvd, source_addr);
	}

	void Source_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		insert_neighbour(&neighbours, source_addr, rcvd->sink_distance_of_sender);
	}

	RECEIVE_MESSAGE_BEGIN(Normal)
		case SourceNode: Source_receieve_Normal(msg, rcvd, source_addr); break;
		case SinkNode: Sink_receieve_Normal(msg, rcvd, source_addr); break;
		case NormalNode: Normal_receieve_Normal(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)


	void x_receieve_Away(message_t* msg, const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);

		insert_neighbour(&neighbours, source_addr, rcvd->sink_distance);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);
			
			METRIC_RCV(Away, rcvd->sink_distance + 1);

			forwarding_message = *rcvd;
			forwarding_message.sink_distance += 1;

			call PacketLink.setRetries(&packet, 0);
			call PacketLink.setRetryDelay(&packet, 0);
			call PacketAcknowledgements.noAck(&packet);

			extra_to_send = 1;
			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);

			call BeaconSenderTimer.startOneShot(beacon_send_wait());
		}

#ifdef SLP_VERBOSE_DEBUG
		print_neighbours("stdout", &neighbours);
#endif
	}

	RECEIVE_MESSAGE_BEGIN(Away)
		case NormalNode: x_receieve_Away(msg, rcvd, source_addr); break;
		case SourceNode: x_receieve_Away(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Away)


	void x_receieve_Beacon(message_t* msg, const BeaconMessage* const rcvd, am_addr_t source_addr)
	{
		insert_neighbour(&neighbours, source_addr, rcvd->sender_sink_distance);
	}

	RECEIVE_MESSAGE_BEGIN(Beacon)
		case NormalNode: x_receieve_Beacon(msg, rcvd, source_addr); break;
		case SourceNode: x_receieve_Beacon(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Beacon)
}
