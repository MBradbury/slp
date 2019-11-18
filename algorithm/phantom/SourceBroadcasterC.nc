#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"
#include "NeighbourDetail.h"
#include "HopDistance.h"

#include "NormalMessage.h"
#include "AwayMessage.h"
#include "BeaconMessage.h"

#include <Timer.h>
#include <TinyError.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, hop_distance_increment(msg->source_distance))
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, hop_distance_increment(msg->landmark_distance))
#define METRIC_RCV_BEACON(msg) METRIC_RCV(Beacon, source_addr, AM_BROADCAST_ADDR, UNKNOWN_SEQNO, UNKNOWN_HOP_DISTANCE)

typedef struct
{
	hop_distance_t distance;
} distance_container_t;

void distance_container_update(distance_container_t* find, distance_container_t const* given)
{
	find->distance = hop_distance_min(find->distance, given->distance);
}

void distance_container_print(const char* name, size_t i, am_addr_t address, distance_container_t const* contents)
{
	simdbg_clear(name, "[%zu] => addr=%u / dist=%d",
		i, address, contents->distance);
}

DEFINE_NEIGHBOUR_DETAIL(distance_container_t, distance, distance_container_update, distance_container_print, SLP_MAX_1_HOP_NEIGHBOURHOOD);

#define UPDATE_NEIGHBOURS(rcvd, source_addr, name) \
{ \
	const distance_container_t dist = {rcvd->name}; \
	insert_distance_neighbour(&neighbours, source_addr, &dist); \
}

#define UPDATE_LANDMARK_DISTANCE(rcvd, name) \
{ \
	landmark_distance = hop_distance_min_nocheck(landmark_distance, hop_distance_increment(rcvd->name)); \
}

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;
	uses interface Crc;

	uses interface Timer<TMilli> as AwaySenderTimer;
	uses interface Timer<TMilli> as BeaconSenderTimer;

	uses interface Packet;
	uses interface AMPacket;

	uses interface SplitControl as RadioControl;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;
	uses interface Receive as NormalSnoop;

	uses interface AMSend as AwaySend;
	uses interface Receive as AwayReceive;

	uses interface AMSend as BeaconSend;
	uses interface Receive as BeaconReceive;

	uses interface MetricLogging;
	uses interface MetricHelpers;

	uses interface NodeType;
	uses interface MessageType;
	uses interface SourcePeriodModel;
	uses interface ObjectDetector;

	uses interface SequenceNumbers as NormalSeqNos;
	uses interface SequenceNumbers as AwaySeqNos;
	 
	uses interface Random;
}

implementation 
{
	typedef enum
	{
		UnknownSet = 0,
		CloserSet = (1 << 0),
		FurtherSet = (1 << 1)
	} SetType;

	hop_distance_t landmark_distance;

	distance_neighbours_t neighbours;

	bool received_beacon;

	bool busy;
	message_t packet;

	uint16_t random_interval(uint16_t min, uint16_t max)
	{
		return min + call Random.rand16() / (UINT16_MAX / (max - min + 1) + 1);
	}

	SetType random_walk_direction(void)
	{
		uint32_t possible_sets = UnknownSet;

		// We want compare sink distance if we do not know our sink distance
		if (landmark_distance != BOTTOM)
		{
			uint32_t i;

			// Find nodes whose sink distance is less than or greater than
			// our sink distance.
			for (i = 0; i != neighbours.size; ++i)
			{
				distance_container_t const* const neighbour = &neighbours.data[i].contents;

				if (landmark_distance < neighbour->distance)
				{
					possible_sets |= FurtherSet;
				}
				else //if (landmark_distance >= neighbour->distance)
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
			// No known neighbours, so have a go at flooding.
			// Someone might get this message
			return UnknownSet;
		}
	}

	am_addr_t random_walk_target(SetType further_or_closer_set, const am_addr_t* to_ignore, size_t to_ignore_length)
	{
		am_addr_t chosen_address;
		uint32_t i;

		distance_neighbours_t local_neighbours;
		init_distance_neighbours(&local_neighbours);

		// If we don't know our sink distance then we cannot work
		// out which neighbour is in closer or further.
		if (landmark_distance != UNKNOWN_HOP_DISTANCE && further_or_closer_set != UnknownSet)
		{
			for (i = 0; i != neighbours.size; ++i)
			{
				distance_neighbour_detail_t const* const neighbour = &neighbours.data[i];

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
						continue;
					}
				}

				//simdbgverbose("stdout", "[%u]: further_or_closer_set=%d, dist=%d neighbour.dist=%d \n",
				//  neighbour->address, further_or_closer_set, landmark_distance, neighbour->contents.distance);

				if ((further_or_closer_set == FurtherSet && landmark_distance < neighbour->contents.distance) ||
					(further_or_closer_set == CloserSet && landmark_distance >= neighbour->contents.distance))
				{
					insert_distance_neighbour(&local_neighbours, neighbour->address, &neighbour->contents);
				}
			}
		}

		if (local_neighbours.size == 0)
		{
			simdbgverbose("stdout", "No local neighbours to choose so broadcasting. (my-dist=%d, my-neighbours-size=%u)\n",
				landmark_distance, neighbours.size);

			chosen_address = AM_BROADCAST_ADDR;
		}
		else
		{
			// Choose a neighbour with equal probabilities.
			const uint16_t rnd = call Random.rand16();
			const uint16_t neighbour_index = rnd % local_neighbours.size;
			const distance_neighbour_detail_t* const neighbour = &local_neighbours.data[neighbour_index];

			chosen_address = neighbour->address;

#ifdef SLP_VERBOSE_DEBUG
			print_distance_neighbours("stdout", &local_neighbours);
#endif

			simdbgverbose("stdout", "Chosen %u at index %u (rnd=%u) out of %u neighbours (their-dist=%d my-dist=%d)\n",
				chosen_address, neighbour_index, rnd, local_neighbours.size,
				neighbour->contents.distance, landmark_distance);
		}

		return chosen_address;
	}

	uint32_t beacon_send_wait(void)
	{
		return 50U + (uint32_t)(random_interval(0, 50));
	}

	USE_MESSAGE_NO_EXTRA_TO_SEND(Normal);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Away);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Beacon);

	event void Boot.booted()
	{
		busy = FALSE;
		call Packet.clear(&packet);

		landmark_distance = UNKNOWN_HOP_DISTANCE;
		received_beacon = FALSE;

		init_distance_neighbours(&neighbours);

		call MessageType.register_pair(NORMAL_CHANNEL, "Normal");
		call MessageType.register_pair(AWAY_CHANNEL, "Away");
		call MessageType.register_pair(BEACON_CHANNEL, "Beacon");

		call NodeType.register_pair(SourceNode, "SourceNode");
		call NodeType.register_pair(SinkNode, "SinkNode");
		call NodeType.register_pair(NormalNode, "NormalNode");

		if (call NodeType.is_node_sink())
		{
			call NodeType.init(SinkNode);
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

			if (call NodeType.is_topology_node_id(LANDMARK_NODE_ID))
			{
				landmark_distance = 0;

				call AwaySenderTimer.startOneShot(AWAY_SEND_PERIOD);
			}
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

			LOG_STDOUT(EVENT_OBJECT_DETECTED, "An object has been detected200\n");

			call SourcePeriodModel.startPeriodic();
		}
	}

	event void ObjectDetector.stoppedDetecting()
	{
		if (call NodeType.get() == SourceNode)
		{
			LOG_STDOUT(EVENT_OBJECT_STOP_DETECTED, "An object has stopped being detected\n");

			call SourcePeriodModel.stop();

			call NodeType.set(NormalNode);
		}
	}

	event void SourcePeriodModel.fired()
	{
		NormalMessage message;
		am_addr_t target;

		simdbgverbose("SourceBroadcasterC", "SourcePeriodModel fired.\n");

#ifdef SLP_VERBOSE_DEBUG
		print_distance_neighbours("stdout", &neighbours);
#endif

		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.source_distance = 0;
		message.landmark_distance_of_sender = landmark_distance;

		message.further_or_closer_set = random_walk_direction();

		target = random_walk_target(message.further_or_closer_set, NULL, 0);

		// If we don't know who our neighbours are, then we
		// cannot unicast to one of them.
		if (target != AM_BROADCAST_ADDR)
		{
			message.broadcast = (target == AM_BROADCAST_ADDR);

			simdbgverbose("stdout", "%s: Forwarding normal from source to target = %u in direction %u\n",
				sim_time_string(), target, message.further_or_closer_set);

			call Packet.clear(&packet);

			if (send_Normal_message(&message, target))
			{
				call NormalSeqNos.increment(TOS_NODE_ID);
			}
		}
		else
		{
			// Broadcasting under this circumstance would be akin to flooding.
			// Which provides no protection.
			//M-SD
			METRIC_GENERIC(METRIC_GENERIC_SOURCE_DROPPED,
				NXSEQUENCE_NUMBER_SPEC "\n",
				message.sequence_number);
		}
	}

	event void AwaySenderTimer.fired()
	{
		const uint32_t now = call AwaySenderTimer.gett0() + call AwaySenderTimer.getdt();

		AwayMessage message;

		if (received_beacon)
		{
			return;
		}

		message.sequence_number = call AwaySeqNos.next(TOS_NODE_ID);
		message.source_id = TOS_NODE_ID;
		message.landmark_distance = landmark_distance;

		if (send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			call AwaySeqNos.increment(TOS_NODE_ID);
		}

		call AwaySenderTimer.startOneShotAt(now, AWAY_SEND_PERIOD);
	}

	event void BeaconSenderTimer.fired()
	{
		BeaconMessage message;

		simdbgverbose("SourceBroadcasterC", "BeaconSenderTimer fired.\n");

		message.landmark_distance_of_sender = landmark_distance;

		send_Beacon_message(&message, AM_BROADCAST_ADDR);
	}

	void process_normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_LANDMARK_DISTANCE(rcvd, landmark_distance_of_sender);
		
		UPDATE_NEIGHBOURS(rcvd, source_addr, landmark_distance_of_sender);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;
			forwarding_message.landmark_distance_of_sender = landmark_distance;

			if (rcvd->source_distance + 1 < RANDOM_WALK_HOPS &&
				!rcvd->broadcast &&
				!(call NodeType.is_topology_node_id(LANDMARK_NODE_ID)))
			{
				am_addr_t target;

				// The previous node(s) were unable to choose a direction,
				// so lets try to work out the direction the message should go in.
				if (forwarding_message.further_or_closer_set == UnknownSet)
				{
					const distance_neighbour_detail_t* neighbour_detail = find_distance_neighbour(&neighbours, source_addr);
					if (neighbour_detail != NULL)
					{
						forwarding_message.further_or_closer_set =
							neighbour_detail->contents.distance < landmark_distance ? FurtherSet : CloserSet;
					}
					else
					{
						forwarding_message.further_or_closer_set = random_walk_direction();
					}

					simdbgverbose("stdout", "%s: Unknown direction, setting to %d\n",
						sim_time_string(), forwarding_message.further_or_closer_set);
				}

				// Get a target, ignoring the node that sent us this message
				target = random_walk_target(forwarding_message.further_or_closer_set, &source_addr, 1);

				forwarding_message.broadcast = (target == AM_BROADCAST_ADDR);

				// A node on the path away from, or towards the landmark node
				// doesn't have anyone to send to.
				// We do not want to broadcast here as it may lead the attacker towards the source.
				if (target == AM_BROADCAST_ADDR)
				{
					// M-PD
					METRIC_GENERIC(METRIC_GENERIC_PATH_DROPPED,
						NXSEQUENCE_NUMBER_SPEC ",%u\n",
						rcvd->sequence_number, rcvd->source_distance);

					ERROR_OCCURRED(ERROR_RSSI_READ_FAILURE,
						"Failed to read RSSI (1 << " STRINGIFY(LOG2SAMPLES) ") times\n");

					return;
				}

				simdbgverbose("stdout", "%s: Forwarding normal from %u to target = %u\n",
					sim_time_string(), TOS_NODE_ID, target);

				call Packet.clear(&packet);

				send_Normal_message(&forwarding_message, target);
			}
			else
			{
				if (!rcvd->broadcast && (rcvd->source_distance + 1 == RANDOM_WALK_HOPS || call NodeType.is_topology_node_id(LANDMARK_NODE_ID)))
				{
					//M-PE
					METRIC_GENERIC(METRIC_GENERIC_PATH_END,
						TOS_NODE_ID_SPEC "," TOS_NODE_ID_SPEC "," NXSEQUENCE_NUMBER_SPEC ",%u\n",
						source_addr, rcvd->source_id, rcvd->sequence_number, rcvd->source_distance + 1);
				}

				// We want other nodes to continue broadcasting
				forwarding_message.broadcast = TRUE;

				send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
			}
		}
	}

	void Normal_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
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
		UPDATE_NEIGHBOURS(rcvd, source_addr, landmark_distance_of_sender);

		UPDATE_LANDMARK_DISTANCE(rcvd, landmark_distance_of_sender);
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SourceNode: Source_receieve_Normal(msg, rcvd, source_addr); break;
		case SinkNode: Sink_receieve_Normal(msg, rcvd, source_addr); break;
		case NormalNode: Normal_receieve_Normal(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)

	// If the sink snoops a normal message, we may as well just deliver it
	void Sink_snoop_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(rcvd, source_addr, landmark_distance_of_sender);

		UPDATE_LANDMARK_DISTANCE(rcvd, landmark_distance_of_sender);

		// TODO: Enable this when the sink can snoop and then correctly
		// respond to a message being received.
		/*if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			simdbgverbose("stdout", "%s: Received unseen Normal by snooping seqno=%u from %u (dsrc=%u).\n",
				sim_time_string(), rcvd->sequence_number, source_addr, rcvd->source_distance + 1);
		}*/
	}

	void x_snoop_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(rcvd, source_addr, landmark_distance_of_sender);

		UPDATE_LANDMARK_DISTANCE(rcvd, landmark_distance_of_sender);

		//simdbgverbose("stdout", "Snooped a normal from %u intended for %u (rcvd-dist=%d, my-dist=%d)\n",
		//  source_addr, call AMPacket.destination(msg), rcvd->landmark_distance_of_sender, landmark_distance);
	}

	// We need to snoop packets that may be unicasted,
	// so the attacker properly responds to them.
	RECEIVE_MESSAGE_BEGIN(Normal, Snoop)
		case SourceNode: x_snoop_Normal(msg, rcvd, source_addr); break;
		case SinkNode: Sink_snoop_Normal(msg, rcvd, source_addr); break;
		case NormalNode: x_snoop_Normal(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)


	void x_receive_Away(message_t* msg, const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(rcvd, source_addr, landmark_distance);

		UPDATE_LANDMARK_DISTANCE(rcvd, landmark_distance);

		if (call AwaySeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			call AwaySeqNos.update(rcvd->source_id, rcvd->sequence_number);
			
			METRIC_RCV_AWAY(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.landmark_distance = hop_distance_increment(rcvd->landmark_distance);

			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);

			call BeaconSenderTimer.startOneShot(beacon_send_wait());
		}

#ifdef SLP_VERBOSE_DEBUG
		print_distance_neighbours("stdout", &neighbours);
#endif
	}

	RECEIVE_MESSAGE_BEGIN(Away, Receive)
		case NormalNode:
		case SourceNode:
		case SinkNode: x_receive_Away(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Away)


	void x_receieve_Beacon(message_t* msg, const BeaconMessage* const rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(rcvd, source_addr, landmark_distance_of_sender);

		UPDATE_LANDMARK_DISTANCE(rcvd, landmark_distance_of_sender);

		METRIC_RCV_BEACON(rcvd);

		received_beacon = TRUE;
	}

	RECEIVE_MESSAGE_BEGIN(Beacon, Receive)
		case NormalNode:
		case SourceNode:
		case SinkNode: x_receieve_Beacon(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Beacon)
}
