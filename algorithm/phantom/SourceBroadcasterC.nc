#include "Constants.h"
#include "NormalMessage.h"
#include "AwayMessage.h"

#include <Timer.h>
#include <TinyError.h>

#include <assert.h>

#define SEND_MESSAGE(NAME) \
bool send_##NAME##_message(const NAME##Message* tosend, am_addr_t target) \
{ \
	if (!busy || tosend == NULL) \
	{ \
		error_t status; \
 \
		void* const void_message = call Packet.getPayload(&packet, sizeof(NAME##Message)); \
		NAME##Message* const message = (NAME##Message*)void_message; \
		if (message == NULL) \
		{ \
			dbgerror("SourceBroadcasterC", "%s: Packet has no payload, or payload is too large.\n", sim_time_string()); \
			return FALSE; \
		} \
 \
		if (tosend != NULL) \
		{ \
			*message = *tosend; \
		} \
		else \
		{ \
			/* Need tosend set, so that the metrics recording works. */ \
			tosend = message; \
		} \
 \
		status = call NAME##Send.send(target, &packet, sizeof(NAME##Message)); \
		if (status == SUCCESS) \
		{ \
			call Leds.led0On(); \
			busy = TRUE; \
 \
			METRIC_BCAST(NAME, "success"); \
 \
			return TRUE; \
		} \
		else \
		{ \
			METRIC_BCAST(NAME, "failed"); \
 \
			return FALSE; \
		} \
	} \
	else \
	{ \
		dbgverbose("SourceBroadcasterC", "%s: Broadcast" #NAME "Timer busy, not sending " #NAME " message.\n", sim_time_string()); \
 \
		METRIC_BCAST(NAME, "busy"); \
 \
		return FALSE; \
	} \
}

#define SEND_DONE(NAME) \
event void NAME##Send.sendDone(message_t* msg, error_t error) \
{ \
	dbgverbose("SourceBroadcasterC", "%s: " #NAME "Send sendDone with status %i.\n", sim_time_string(), error); \
 \
	if (&packet == msg) \
	{ \
		if (extra_to_send > 0) \
		{ \
			if (send_##NAME##_message(NULL, call AMPacket.destination(msg))) \
			{ \
				--extra_to_send; \
			} \
			else \
			{ \
				call Leds.led0Off(); \
				busy = FALSE; \
			} \
		} \
		else \
		{ \
			call Leds.led0Off(); \
			busy = FALSE; \
		} \
	} \
}

#define RECEIVE_MESSAGE_BEGIN(NAME) \
event message_t* NAME##Receive.receive(message_t* msg, void* payload, uint8_t len) \
{ \
	const NAME##Message* const rcvd = (const NAME##Message*)payload; \
 \
	const am_addr_t source_addr = call AMPacket.source(msg); \
 \
	dbg_clear("Attacker-RCV", "%" PRIu64 ",%s,%u,%u,%u\n", sim_time(), #NAME, TOS_NODE_ID, source_addr, rcvd->sequence_number); \
 \
	if (len != sizeof(NAME##Message)) \
	{ \
		dbgerror("SourceBroadcasterC", "%s: Received " #NAME " of invalid length %hhu.\n", sim_time_string(), len); \
		return msg; \
	} \
 \
	dbgverbose("SourceBroadcasterC", "%s: Received valid " #NAME ".\n", sim_time_string()); \
 \
	switch (type) \
	{

#define RECEIVE_MESSAGE_END(NAME) \
		default: \
		{ \
			dbgerror("SourceBroadcasterC", "%s: Unknown node type %s. Cannot process " #NAME " message\n", sim_time_string(), type_to_string()); \
		} break; \
	} \
 \
	return msg; \
}

#define METRIC_RCV(TYPE, DISTANCE) \
	dbg_clear("Metric-RCV", "%s,%" PRIu64 ",%u,%u,%u,%u\n", #TYPE, sim_time(), TOS_NODE_ID, source_addr, rcvd->sequence_number, DISTANCE)

#define METRIC_BCAST(TYPE, STATUS) \
	dbg_clear("Metric-BCAST", "%s,%" PRIu64 ",%u,%s,%u\n", #TYPE, sim_time(), TOS_NODE_ID, STATUS, (tosend != NULL) ? tosend->sequence_number : (uint32_t)-1)


typedef struct
{
	am_addr_t address;
	int16_t sink_distance;
	uint16_t received_count;
	float rssi_average;
} NeighbourDetail;

enum { MaxNeighbours = 10 };

typedef struct
{
	NeighbourDetail data[MaxNeighbours];
	uint32_t size;
} Neighbours;

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;

	uses interface LocalTime<TMilli>;
	uses interface Timer<TMilli> as BroadcastNormalTimer;
	uses interface Timer<TMilli> as AwaySenderTimer;

	uses interface Packet;
	uses interface AMPacket;
	uses interface TossimPacket;

	uses interface SplitControl as RadioControl;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;

	uses interface AMSend as AwaySend;
	uses interface Receive as AwayReceive;

	uses interface ObjectDetector;
	 
	uses interface Random;
}

implementation 
{
	void init_neighbours(Neighbours* neighbours)
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

	bool insert_neighbour(Neighbours* neighbours, am_addr_t address, int16_t sink_distance, message_t* msg)
	{
		NeighbourDetail* find = find_neighbour(neighbours, address);

		const int8_t rssi = msg == NULL ? 0 : call TossimPacket.strength(msg);

		if (find != NULL)
		{
			find->sink_distance = minbot(find->sink_distance, sink_distance);
			find->received_count += 1;
			find->rssi_average += (rssi - find->rssi_average) / find->received_count;
		}
		else
		{
			if (neighbours->size < MaxNeighbours)
			{
				find = &neighbours->data[neighbours->size];

				find->address = address;
				find->sink_distance = sink_distance;
				find->received_count = 1;
				find->rssi_average = rssi;

				neighbours->size += 1;
			}
		}

		return find != NULL;
	}

	void print_neighbours(char * name, Neighbours const* neighbours)
	{
		uint32_t i;
		dbg(name, "Neighbours(size=%d, values=", neighbours->size);
		for (i = 0; i != neighbours->size; ++i)
		{
			NeighbourDetail const* neighbour = &neighbours->data[i];
			dbg_clear(name, "[%u] => %u / %d / %u / %f",
				i, neighbour->address, neighbour->sink_distance,
				neighbour->received_count, neighbour->rssi_average);

			if ((i + 1) != neighbours->size)
			{
				dbg_clear(name, ", ");
			}
		}
		dbg_clear(name, ")\n");
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


	NormalMessage repeat_message;
	am_addr_t repeat_target;
	uint32_t repeat_count;

	bool busy = FALSE;
	message_t packet;

	uint32_t extra_to_send = 0;

	// This function is to be used by the source node to get the
	// period it should use at the current time.
	// DO NOT use this for nodes other than the source!
	uint32_t get_source_period()
	{
		typedef struct {
			uint32_t end;
			uint32_t period;
		} local_end_period_t;

		const local_end_period_t times[] = PERIOD_TIMES_MS;
		const uint32_t else_time = PERIOD_ELSE_TIME_MS;

		const unsigned int times_length = ARRAY_LENGTH(times);

		const uint32_t current_time = call LocalTime.get();

		unsigned int i;

		uint32_t period = -1;

		assert(type == SourceNode);

		dbgverbose("stdout", "Called get_source_period current_time=%u #times=%u\n",
			current_time, times_length);

		for (i = 0; i != times_length; ++i)
		{
			//dbgverbose("stdout", "i=%u current_time=%u end=%u period=%u\n",
			//	i, current_time, times[i].end, times[i].period);

			if (current_time < times[i].end)
			{
				period = times[i].period;
				break;
			}
		}

		if (i == times_length)
		{
			period = else_time;
		}

		dbgverbose("stdout", "Providing source period %u at time=%u\n",
			period, current_time);
		return period;
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

		assert(type == SourceNode);

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
			return UnknownSet;
		}
	}

	am_addr_t random_walk_target(NormalMessage const* rcvd)
	{
		am_addr_t chosen_address;
		uint32_t i;

		Neighbours local_neighbours;
		init_neighbours(&local_neighbours);

		if (sink_distance != BOTTOM)
		{
			for (i = 0; i != neighbours.size; ++i)
			{
				NeighbourDetail const* const neighbour = &neighbours.data[i];

				//dbgverbose("stdout", "[%u]: further_or_closer_set=%d, dsink=%d neighbour.dsink=%d \n",
				//	neighbour->address, rcvd->further_or_closer_set, sink_distance, neighbour->sink_distance);

				if ((rcvd->further_or_closer_set == FurtherSet && sink_distance <= neighbour->sink_distance) ||
					(rcvd->further_or_closer_set == CloserSet && sink_distance >= neighbour->sink_distance))
				{
					insert_neighbour(&local_neighbours, neighbour->address, neighbour->sink_distance, NULL);
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
			const uint16_t rnd = call Random.rand16() % local_neighbours.size;

			chosen_address = local_neighbours.data[rnd].address;
		}

		return chosen_address;
	}


	SEND_MESSAGE(Normal);
	SEND_MESSAGE(Away);

	SEND_DONE(Normal);
	SEND_DONE(Away);
	

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
				call AwaySenderTimer.startOneShot(1000);
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

		dbgverbose("SourceBroadcasterC", "%s: BroadcastNormalTimer fired.\n", sim_time_string());

		message.sequence_number = sequence_number_next(&normal_sequence_counter);
		message.source_distance = 0;
		message.sink_distance_of_sender = sink_distance;

		message.further_or_closer_set = random_walk_direction();

		target = random_walk_target(&message);

		dbgverbose("stdout", "%s: Forwarding normal from source to target = %u in direction %u\n",
			sim_time_string(), target, message.further_or_closer_set);

		extra_to_send = 1;
		if (send_Normal_message(&message, target))
		{
			sequence_number_increment(&normal_sequence_counter);
		}

		call BroadcastNormalTimer.startOneShot(get_source_period());
	}

	event void AwaySenderTimer.fired()
	{
		AwayMessage message;

		dbgverbose("SourceBroadcasterC", "%s: AwaySenderTimer fired.\n", sim_time_string());

		sink_distance = 0;

		message.sequence_number = sequence_number_next(&away_sequence_counter);
		message.sink_distance = sink_distance;

		extra_to_send = 2;
		if (send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			sequence_number_increment(&away_sequence_counter);
		}

		dbgverbose("stdout", "Away sent\n");
	}	

	void Normal_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		insert_neighbour(&neighbours, source_addr, rcvd->sink_distance_of_sender, msg);

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
				const am_addr_t target = random_walk_target(&forwarding_message);

				dbgverbose("stdout", "%s: Forwarding normal from %u to target = %u\n",
					sim_time_string(), TOS_NODE_ID, target);

				//extra_to_send = 3;
				send_Normal_message(&forwarding_message, target);
			}
			else
			{
				send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
			}
		}
	}

	void Sink_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		insert_neighbour(&neighbours, source_addr, rcvd->sink_distance_of_sender, msg);

		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Normal, rcvd->source_distance + 1);
		}
	}

	void Source_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		insert_neighbour(&neighbours, source_addr, rcvd->sink_distance_of_sender, msg);
	}

	RECEIVE_MESSAGE_BEGIN(Normal)
		case SourceNode: Source_receieve_Normal(msg, rcvd, source_addr); break;
		case SinkNode: Sink_receieve_Normal(msg, rcvd, source_addr); break;
		case NormalNode: Normal_receieve_Normal(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)


	void x_receieve_Away(message_t* msg, const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);

		insert_neighbour(&neighbours, source_addr, rcvd->sink_distance, msg);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);
			
			METRIC_RCV(Away, rcvd->sink_distance + 1);

			forwarding_message = *rcvd;
			forwarding_message.sink_distance += 1;

			extra_to_send = 1;
			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);
		}

		print_neighbours("stdout", &neighbours);
	}  

	RECEIVE_MESSAGE_BEGIN(Away)
		case NormalNode: x_receieve_Away(msg, rcvd, source_addr); break;
		case SourceNode: x_receieve_Away(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Away)
}
