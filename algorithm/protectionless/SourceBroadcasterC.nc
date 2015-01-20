#include "Constants.h"
#include "NormalMessage.h"
#include "SequenceNumber.h"

#include <Timer.h>
#include <TinyError.h>

#ifdef SLP_VERBOSE_DEBUG
#	define dbgverbose(...) dbg(__VA_ARGS__)
#else
#	define dbgverbose(...)
#endif

#define SEND_MESSAGE(NAME) \
bool send_##NAME##_message(const NAME##Message* tosend) \
{ \
	error_t status; \
 \
	if (!busy) \
	{ \
		void* const void_message = call Packet.getPayload(&packet, sizeof(NAME##Message)); \
		NAME##Message* const message = (NAME##Message*)void_message; \
		if (message == NULL) \
		{ \
			dbgerror("SourceBroadcasterC", "%s: Packet has no payload, or payload is too large.\n", sim_time_string()); \
			return FALSE; \
		} \
 \
		*message = *tosend; \
 \
		status = call NAME##Send.send(AM_BROADCAST_ADDR, &packet, sizeof(NAME##Message)); \
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
		call Leds.led0Off(); \
		busy = FALSE; \
	} \
}

#define RECEIVE_MESSAGE_BEGIN(NAME) \
event message_t* NAME##Receive.receive(message_t* msg, void* payload, uint8_t len) \
{ \
	const NAME##Message* const rcvd = (const NAME##Message*)payload; \
 \
	const am_addr_t source_addr = call AMPacket.source(msg); \
 \
	dbg_clear("Attacker-RCV", "%" PRIu64 ",%u,%u,%u,%u\n", sim_time(), #NAME, TOS_NODE_ID, source_addr, rcvd->sequence_number); \
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
	dbg_clear("Metric-BCAST", "%s,%" PRIu64 ",%u,%s,%u\n", #TYPE, sim_time(), TOS_NODE_ID, STATUS, tosend->sequence_number)

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;

	uses interface Timer<TMilli> as BroadcastNormalTimer;

	uses interface Packet;
	uses interface AMPacket;

	uses interface SplitControl as RadioControl;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;
}

implementation
{
	typedef enum
	{
		SourceNode, SinkNode, NormalNode
	} NodeType;

	NodeType type = NormalNode;

	const char* type_to_string()
	{
		switch (type)
		{
		case SourceNode: 			return "SourceNode";
		case SinkNode:				return "SinkNode  ";
		case NormalNode:			return "NormalNode";
		default:					return "<unknown> ";
		}
	}

	SequenceNumber normal_sequence_counter;

	bool busy = FALSE;
	message_t packet;

	event void Boot.booted()
	{
		dbgverbose("Boot", "%s: Application booted.\n", sim_time_string());

		sequence_number_init(&normal_sequence_counter);

		if (TOS_NODE_ID == SOURCE_NODE_ID)
		{
			type = SourceNode;
		}
		if (TOS_NODE_ID == SINK_NODE_ID)
		{
			type = SinkNode;
		}

		call RadioControl.start();
	}

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			dbgverbose("SourceBroadcasterC", "%s: RadioControl started.\n", sim_time_string());

			if (type == SourceNode)
			{
				call BroadcastNormalTimer.startPeriodic(SOURCE_PERIOD_MS);
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

	SEND_DONE(Normal);

	SEND_MESSAGE(Normal);

	event void BroadcastNormalTimer.fired()
	{
		NormalMessage message;

		dbgverbose("SourceBroadcasterC", "%s: BroadcastNormalTimer fired.\n", sim_time_string());

		message.sequence_number = sequence_number_next(&normal_sequence_counter);
		message.source_distance = 0;
		message.source_id = TOS_NODE_ID;

		if (send_Normal_message(&message))
		{
			sequence_number_increment(&normal_sequence_counter);
		}
	}

	void Normal_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			NormalMessage forwarding_message;

			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Normal, rcvd->source_distance + 1);

			dbgverbose("SourceBroadcasterC", "%s: Received unseen Normal seqno=%u from %u.\n", sim_time_string(), rcvd->sequence_number, source_addr);

			forwarding_message = *rcvd;
			forwarding_message.source_distance += 1;

			send_Normal_message(&forwarding_message);
		}
	}

	void Sink_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV(Normal, rcvd->source_distance + 1);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal)
		case SinkNode: Sink_receive_Normal(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Normal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)
}
