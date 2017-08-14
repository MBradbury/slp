#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "NeighbourDetail.h"

#include "NormalMessage.h"
#include "AwayMessage.h"
#include "DisableMessage.h"
#include "ActivateMessage.h"
#include "BeaconMessage.h"
#include "PollMessage.h"

#include <Timer.h>
#include <TinyError.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_AWAY(msg) METRIC_RCV(Away, source_addr, msg->source_id, msg->sequence_number, msg->sink_distance + 1)
#define METRIC_RCV_DISABLE(msg) METRIC_RCV(Disable, source_addr, msg->source_id, msg->sequence_number, BOTTOM)
#define METRIC_RCV_ACTIVATE(msg) METRIC_RCV(Activate, source_addr, msg->source_id, msg->sequence_number, msg->sink_distance + 1)
#define METRIC_RCV_BEACON(msg) METRIC_RCV(Beacon, source_addr, BOTTOM, UNKNOWN_SEQNO, BOTTOM)
#define METRIC_RCV_POLL(msg) METRIC_RCV(Poll, source_addr, BOTTOM, UNKNOWN_SEQNO, BOTTOM)

void ni_update(ni_container_t* find, ni_container_t const* given)
{
	find->sink_distance = minbot(find->sink_distance, given->sink_distance);
	find->source_distance = minbot(find->source_distance, given->source_distance);
}

void ni_print(const char* name, size_t i, am_addr_t address, ni_container_t const* contents)
{
	simdbg_clear(name, "(%zu) %u: sink-dist=%d src-dist=%d",
		i, address, contents->sink_distance, contents->source_distance);
}

DEFINE_NEIGHBOUR_DETAIL(ni_container_t, ni, ni_update, ni_print, SLP_MAX_1_HOP_NEIGHBOURHOOD);

#define UPDATE_NEIGHBOURS(source_addr, sink_distance, source_distance) \
{ \
	const ni_container_t dist = { sink_distance, source_distance }; \
	call Neighbours.record(source_addr, &dist); \
}

#define CHOOSE_NEIGHBOURS_WITH_PREDICATE(PRED) \
if (local_neighbours.size == 0) \
{ \
	const am_addr_t* iter; \
	const am_addr_t* end; \
	for (iter = call Neighbours.beginKeys(), end = call Neighbours.endKeys(); iter != end; ++iter) \
	{ \
		const am_addr_t address = *iter; \
		ni_container_t const* const neighbour = call Neighbours.get_from_iter(iter); \
 \
		if (PRED) \
		{ \
			insert_ni_neighbour(&local_neighbours, address, neighbour); \
		} \
	} \
}

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;
	uses interface Random;

	uses interface Packet;
	uses interface AMPacket;

	uses interface SplitControl as RadioControl;

	uses interface Timer<TMilli> as AwaySenderTimer;
	uses interface Timer<TMilli> as DisableSenderTimer;
	uses interface Timer<TMilli> as ActivateSenderTimer;
	uses interface Timer<TMilli> as ActivateExpiryTimer;
	uses interface Timer<TMilli> as ActivateBackoffTimer;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;

	uses interface AMSend as AwaySend;
	uses interface Receive as AwayReceive;

	uses interface AMSend as DisableSend;
	uses interface Receive as DisableReceive;

	uses interface AMSend as ActivateSend;
	uses interface Receive as ActivateReceive;
	uses interface Receive as ActivateSnoop;
	uses interface PacketAcknowledgements as ActivatePacketAcknowledgements;

	uses interface MetricLogging;

	uses interface Neighbours<ni_container_t, BeaconMessage, PollMessage>;

	uses interface NodeType;
	uses interface MessageType;
	uses interface ObjectDetector;
	uses interface SourcePeriodModel;

	uses interface SequenceNumbers as NormalSeqNos;
}

implementation
{
	enum
	{
		SourceNode, SinkNode, NormalNode
	};

	bool busy;
	message_t packet;

	SequenceNumber away_sequence_counter;
	SequenceNumber disable_sequence_counter;
	SequenceNumber activate_sequence_counter;

	int32_t sink_distance;
	int32_t source_distance;

	int32_t disable_radius;

	int away_messages_to_send;

	bool sent_disable;

	bool process_messages;

	am_addr_t previously_sent_to;

	ActivateMessage current_activate_message;

	void disable_normal_forward(void)
	{
		call Leds.led2Off();
		process_messages = FALSE;
	}

	void enable_normal_forward(void)
	{
		call Leds.led2On();
		process_messages = TRUE;
	}

	void enable_normal_forward_with_timeout(void)
	{
		if (!process_messages || call ActivateExpiryTimer.isRunning())
		{
			enable_normal_forward();
			call ActivateExpiryTimer.startOneShot(ACTIVATE_EXPIRY_PERIOD_MS);
		}
	}

	event void Boot.booted()
	{
		LOG_STDOUT_VERBOSE(EVENT_BOOTED, "booted\n");

		busy = FALSE;
		call Packet.clear(&packet);

		sequence_number_init(&away_sequence_counter);
		sequence_number_init(&disable_sequence_counter);
		sequence_number_init(&activate_sequence_counter);

		sink_distance = BOTTOM;
		source_distance = BOTTOM;

		disable_radius = BOTTOM;

		away_messages_to_send = 3;

		sent_disable = FALSE;

		enable_normal_forward();

		previously_sent_to = AM_BROADCAST_ADDR;

		call MessageType.register_pair(NORMAL_CHANNEL, "Normal");
		call MessageType.register_pair(AWAY_CHANNEL, "Away");
		call MessageType.register_pair(DISABLE_CHANNEL, "Disable");
		call MessageType.register_pair(ACTIVATE_CHANNEL, "Activate");
		call MessageType.register_pair(POLL_CHANNEL, "Poll");
		call MessageType.register_pair(BEACON_CHANNEL, "Beacon");

		call NodeType.register_pair(SourceNode, "SourceNode");
		call NodeType.register_pair(SinkNode, "SinkNode");
		call NodeType.register_pair(NormalNode, "NormalNode");

		if (call NodeType.is_node_sink())
		{
			call NodeType.init(SinkNode);
			sink_distance = 0;

			call AwaySenderTimer.startOneShot(5 * AWAY_DELAY_MS);
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

			call ObjectDetector.start_later(SLP_OBJECT_DETECTOR_START_DELAY_MS);
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

			source_distance = 0;

			LOG_STDOUT(EVENT_OBJECT_DETECTED, "An object has been detected\n");

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

	USE_MESSAGE_NO_EXTRA_TO_SEND(Normal);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Away);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Disable);
	USE_MESSAGE_ACK_REQUEST_WITH_CALLBACK(Activate);

	event void SourcePeriodModel.fired()
	{
		NormalMessage message;

		simdbgverbose("SourceBroadcasterC", "SourcePeriodModel fired.\n");

		message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
		message.source_distance = 0;
		message.source_id = TOS_NODE_ID;

		if (send_Normal_message(&message, AM_BROADCAST_ADDR))
		{
			call NormalSeqNos.increment(TOS_NODE_ID);
		}
	}

	event void ActivateExpiryTimer.fired()
	{
		disable_normal_forward();
	}

	event void AwaySenderTimer.fired()
	{
		AwayMessage message;
		message.sequence_number = sequence_number_next(&away_sequence_counter);
		message.source_id = TOS_NODE_ID;
		message.sink_distance = 0;

		if (send_Away_message(&message, AM_BROADCAST_ADDR))
		{
			sequence_number_increment(&away_sequence_counter);

			away_messages_to_send -= 1;

			if (away_messages_to_send > 0)
			{
				call AwaySenderTimer.startOneShot(AWAY_DELAY_MS);
			}
		}
		else
		{
			call AwaySenderTimer.startOneShot(AWAY_DELAY_MS);
		}
	}

	event void DisableSenderTimer.fired()
	{
		DisableMessage disable_message;
		disable_message.sequence_number = sequence_number_next(&disable_sequence_counter);
		disable_message.source_id = TOS_NODE_ID;
		disable_message.hop_limit = (int16_t)disable_radius;
		disable_message.sink_source_distance = source_distance;

		if (send_Disable_message(&disable_message, AM_BROADCAST_ADDR))
		{
			sequence_number_increment(&disable_sequence_counter);
		}
		else
		{
			call DisableSenderTimer.startOneShot(25);
		}
	}

	task void send_activate();

	event void ActivateSenderTimer.fired()
	{
#ifdef ACTIVATE_RANDOMLY_CHANGES
		call ActivateSenderTimer.startOneShot(ACTIVATE_PERIOD_MS);
#endif

		current_activate_message.sequence_number = sequence_number_next(&activate_sequence_counter);
		current_activate_message.source_id = TOS_NODE_ID;
		current_activate_message.sink_distance = 0;
		current_activate_message.previous_normal_forward_enabled = TRUE;

		sequence_number_increment(&activate_sequence_counter);

		post send_activate();
	}

	event void ActivateBackoffTimer.fired()
	{
		post send_activate();
	}

	ni_neighbour_detail_t* choose_random_neighbour(ni_neighbours_t* local_neighbours)
	{
		uint16_t rnd = call Random.rand16();
		uint16_t neighbour_index = rnd % local_neighbours->size;
		ni_neighbour_detail_t* neighbour = &local_neighbours->data[neighbour_index];

		// Try once more, to avoid always selecting the same target
		if (local_neighbours->size > 1 && neighbour->address == previously_sent_to)
		{
			rnd = call Random.rand16();
			neighbour_index = rnd % local_neighbours->size;
			neighbour = &local_neighbours->data[neighbour_index];
		}

		return neighbour;
	}

	bool choose_activate_target(am_addr_t* next)
	{
		bool success = FALSE;

		ni_neighbours_t local_neighbours;
		init_ni_neighbours(&local_neighbours);

#ifdef ACTIVATE_RANDOMLY_CHANGES
		CHOOSE_NEIGHBOURS_WITH_PREDICATE(neighbour->sink_distance > sink_distance)
		CHOOSE_NEIGHBOURS_WITH_PREDICATE(neighbour->sink_distance == sink_distance)
#else
		CHOOSE_NEIGHBOURS_WITH_PREDICATE(neighbour->sink_distance > sink_distance && neighbour->source_distance > source_distance)
		CHOOSE_NEIGHBOURS_WITH_PREDICATE(neighbour->sink_distance >= sink_distance && neighbour->source_distance > source_distance)
		CHOOSE_NEIGHBOURS_WITH_PREDICATE(neighbour->sink_distance >= sink_distance && neighbour->source_distance >= source_distance)
#endif

		if (local_neighbours.size > 0)
		{
			const ni_neighbour_detail_t* const neighbour = choose_random_neighbour(&local_neighbours);

			*next = neighbour->address;
			success = TRUE;
		}

		return success;
	}

	task void send_activate()
	{
		am_addr_t target = AM_BROADCAST_ADDR;
		const bool target_success = choose_activate_target(&target);

		if (!target_success)
		{
			PollMessage poll_message;
			poll_message.sink_distance_of_sender= sink_distance;
			poll_message.source_distance_of_sender = source_distance;

			call Neighbours.poll(&poll_message);
			call ActivateBackoffTimer.startOneShot(25);
		}
		else
		{
			bool ack_requested = (target != AM_BROADCAST_ADDR);

			if (send_Activate_message(&current_activate_message, target, &ack_requested))
			{
			}
			else
			{
				call ActivateBackoffTimer.startOneShot(25);
			}
		}
	}
	
	void send_Activate_done(message_t* msg, error_t error)
	{
		if (error != SUCCESS)
		{
			call ActivateBackoffTimer.startOneShot(25);
		}
		else
		{
			const am_addr_t target = call AMPacket.destination(msg);

			const bool ack_requested = (target != AM_BROADCAST_ADDR);
			const bool was_acked = call ActivatePacketAcknowledgements.wasAcked(msg);

			if (ack_requested & !was_acked)
			{
				call Neighbours.rtx_result(target, FALSE);

				call ActivateBackoffTimer.startOneShot(25);
			}
			else
			{
				previously_sent_to = target;

				if (ack_requested & was_acked)
				{
					call Neighbours.rtx_result(target, TRUE);
				}
			}
		}
	}

	void Normal_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		source_distance = minbot(source_distance, rcvd->source_distance + 1);

		UPDATE_NEIGHBOURS(source_addr, BOTTOM, rcvd->source_distance);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			simdbgverbose("SourceBroadcasterC", "Received unseen Normal seqno=" NXSEQUENCE_NUMBER_SPEC " from %u.\n",
				rcvd->sequence_number, source_addr);

			if (process_messages)
			{
				NormalMessage forwarding_message = *rcvd;
				forwarding_message.source_distance += 1;

				send_Normal_message(&forwarding_message, AM_BROADCAST_ADDR);
			}
		}
	}

	void Sink_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		source_distance = minbot(source_distance, rcvd->source_distance + 1);

		UPDATE_NEIGHBOURS(source_addr, BOTTOM, rcvd->source_distance);

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			if (!sent_disable)
			{
#ifdef ACTIVATE_RANDOMLY_CHANGES
				//disable_radius = (int32_t)ceil((source_distance + CONE_WIDTH/2.0) / (M_PI / 2));
				disable_radius = (int32_t)ceil((2 * source_distance + CONE_WIDTH) / M_PI);
#else
				// This equation is for when the path that is activated is always away from
				// the sink and source. If paths towards the source exist, then this should
				// be larger.
				disable_radius = (int32_t)ceil((source_distance + CONE_WIDTH/2.0) / M_PI);
#endif

				//disable_radius = min(disable_radius, source_distance/2);

				LOG_STDOUT(ERROR_UNKNOWN, "Disable radius is %u Dsrc/2 is %d\n", disable_radius, source_distance/2);

				call DisableSenderTimer.startOneShot(25);
				call ActivateSenderTimer.startOneShot(100);

				sent_disable = TRUE;
			}
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
		case SinkNode: Sink_receive_Normal(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Normal(rcvd, source_addr); break;
		case SourceNode: break;
	RECEIVE_MESSAGE_END(Normal)


	void x_receive_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);

		UPDATE_NEIGHBOURS(source_addr, rcvd->sink_distance, BOTTOM);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			AwayMessage forwarding_message;

			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_AWAY(rcvd);

			forwarding_message = *rcvd;
			forwarding_message.sink_distance += 1;

			send_Away_message(&forwarding_message, AM_BROADCAST_ADDR);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Away, Receive)
		case SinkNode:
		case NormalNode: x_receive_Away(rcvd, source_addr); break;
		case SourceNode: break;
	RECEIVE_MESSAGE_END(Away)


	void Normal_receive_Disable(const DisableMessage* const rcvd, am_addr_t source_addr)
	{
		if (sequence_number_before(&disable_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&disable_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_DISABLE(rcvd);

			if (rcvd->hop_limit > 0)
			{
				DisableMessage forwarding_message = *rcvd;

				send_Disable_message(&forwarding_message, AM_BROADCAST_ADDR);
			}

			if (
				// Create the inner protected ring and the outer disabled ring of nodes
				sink_distance != BOTTOM && sink_distance > PROTECTED_SINK_HOPS && sink_distance <= rcvd->hop_limit &&

				// Protect nodes by the source
				source_distance != BOTTOM && source_distance > 1)
			{
				disable_normal_forward();
			}
		}
	}

	RECEIVE_MESSAGE_BEGIN(Disable, Receive)
		case SinkNode: break;
		case NormalNode: Normal_receive_Disable(rcvd, source_addr); break;
		case SourceNode: break;
	RECEIVE_MESSAGE_END(Disable)


	void Normal_receive_Activate(const ActivateMessage* const rcvd, am_addr_t source_addr)
	{
		sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);

		UPDATE_NEIGHBOURS(source_addr, rcvd->sink_distance, BOTTOM);

		if (sequence_number_before(&activate_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&activate_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_ACTIVATE(rcvd);

			// If we are coming from a disabled node and we are enabled, stop sending active message
			//if (rcvd->previous_normal_forward_enabled || !process_messages)
			{
				current_activate_message = *rcvd;
				current_activate_message.sink_distance += 1;
				current_activate_message.previous_normal_forward_enabled = process_messages;

				post send_activate();
			}

#ifdef ACTIVATE_RANDOMLY_CHANGES
			enable_normal_forward_with_timeout();
#else
			enable_normal_forward();
#endif
		}
	}

	RECEIVE_MESSAGE_BEGIN(Activate, Receive)
		case SinkNode: break;
		case NormalNode: Normal_receive_Activate(rcvd, source_addr); break;
		case SourceNode: break;
	RECEIVE_MESSAGE_END(Activate)


	void Normal_snoop_Activate(const ActivateMessage* const rcvd, am_addr_t source_addr)
	{
		sink_distance = minbot(sink_distance, rcvd->sink_distance + 1);

		UPDATE_NEIGHBOURS(source_addr, rcvd->sink_distance, BOTTOM);

		if (sequence_number_before(&activate_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&activate_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_ACTIVATE(rcvd);

#ifdef CONE_TYPE_WITH_SNOOP
#	ifdef ACTIVATE_RANDOMLY_CHANGES
			enable_normal_forward_with_timeout();
#	else
			enable_normal_forward();
#	endif
#endif
		}
	}

	RECEIVE_MESSAGE_BEGIN(Activate, Snoop)
		case SinkNode: break;
		case NormalNode: Normal_snoop_Activate(rcvd, source_addr); break;
		case SourceNode: break;
	RECEIVE_MESSAGE_END(Activate)



	// Neighbour management

	event void Neighbours.perform_update(ni_container_t* find, const ni_container_t* given)
	{
		ni_update(find, given);
	}

	event void Neighbours.generate_beacon(BeaconMessage* message)
	{
		message->sink_distance_of_sender = sink_distance;
		message->source_distance_of_sender = source_distance;
	}

	event void Neighbours.rcv_poll(const PollMessage* rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(source_addr, rcvd->sink_distance_of_sender, rcvd->source_distance_of_sender);

		METRIC_RCV_POLL(rcvd);

		sink_distance = minbot(sink_distance, botinc(rcvd->sink_distance_of_sender));
		source_distance = minbot(source_distance, botinc(rcvd->source_distance_of_sender));
	}

	event void Neighbours.rcv_beacon(const BeaconMessage* rcvd, am_addr_t source_addr)
	{
		UPDATE_NEIGHBOURS(source_addr, rcvd->sink_distance_of_sender, rcvd->source_distance_of_sender);

		METRIC_RCV_BEACON(rcvd);

		sink_distance = minbot(sink_distance, botinc(rcvd->sink_distance_of_sender));
		source_distance = minbot(source_distance, botinc(rcvd->source_distance_of_sender));
	}
}
