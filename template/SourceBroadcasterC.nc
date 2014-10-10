#include "AwayChooseMessage.h"
#include "Constants.h"
#include "FakeMessage.h"
#include "NormalMessage.h"
#include "SequenceNumber.h"

#include <Timer.h>
#include <TinyError.h>

#define max(a, b) \
	({ __typeof__(a) _a = (a); \
	   __typeof__(b) _b = (b); \
	   _a > _b ? _a : _b; })

#define min(a, b) \
	({ __typeof__(a) _a = (a); \
	   __typeof__(b) _b = (b); \
	   _a < _b ? _a : _b; })

#define minbot(a, b) \
	({ __typeof__(a) _a = (a); \
	   __typeof__(b) _b = (b); \
	   (_a == BOTTOM || _b < _a) ? _b : _a; })


#define SEND_MESSAGE(NAME) \
bool send_##NAME##_message(const NAME##Message* tosend) \
{ \
	error_t status; \
 \
	if (!busy) \
	{ \
		NAME##Message* const message = (NAME##Message*)(call Packet.getPayload(&packet, sizeof(NAME##Message))); \
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
			dbg_clear("Metric-BCAST-" #NAME, "%" PRIu64 ",%u,%s,%u\n", sim_time(), TOS_NODE_ID, "success", tosend->sequence_number); \
 \
			return TRUE; \
		} \
		else \
		{ \
			dbg_clear("Metric-BCAST-" #NAME, "%" PRIu64 ",%u,%s,%u\n", sim_time(), TOS_NODE_ID, "failed", tosend->sequence_number); \
 \
			return FALSE; \
		} \
	} \
	else \
	{ \
		dbg("SourceBroadcasterC", "%s: Broadcast" #NAME "Timer busy, not sending " #NAME " message.\n", sim_time_string()); \
 \
		dbg_clear("Metric-BCAST-" #NAME, "%" PRIu64 ",%u,%s,%u\n", sim_time(), TOS_NODE_ID, "busy", tosend->sequence_number); \
 \
		return FALSE; \
	} \
}

#define SEND_DONE(NAME) \
event void NAME##Send.sendDone(message_t* msg, error_t error) \
{ \
	dbg("SourceBroadcasterC", "%s: " #NAME "Send sendDone with status %i.\n", sim_time_string(), error); \
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
	dbg("SourceBroadcasterC", "%s: Received valid " #NAME ".\n", sim_time_string()); \
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

	uses interface AMSend as AwaySend;
	uses interface Receive as AwayReceive;

	uses interface AMSend as ChooseSend;
	uses interface Receive as ChooseReceive;

	uses interface AMSend as FakeSend;
	uses interface Receive as FakeReceive;
}

implementation
{
	typedef enum
	{
		SourceNode, SinkNode, NormalNode, TempFakeNode, PermFakeNode
	} NodeType;

	NodeType type = NormalNode;

	const char* type_to_string()
	{
		switch (type)
		{
		case SourceNode: 			return "SourceNode";
		case SinkNode:				return "SinkNode  ";
		case NormalNode:			return "NormalNode";
		case TempFakeNode:			return "TempFakeNode";
		case PermFakeNode:			return "PermFakeNode";
		default:					return "<unknown> ";
		}
	}

	SequenceNumber normal_sequence_counter;
	SequenceNumber away_sequence_counter;
	SequenceNumber choose_sequence_counter;
	SequenceNumber fake_sequence_counter;

	int32_t sink_source_distance = BOTTOM;
	int32_t source_distance = BOTTOM;
	int32_t sink_distance = BOTTOM;

	bool sink_sent_away = FALSE;
	bool seen_pfs = FALSE;
	bool is_pfs_candidate = FALSE;

	int32_t first_source_distance = BOTTOM;

	typedef enum
	{
		UnknownAlgorithm, GenericAlgorithm, FurtherAlgorithm
	} Algorithm;

	Algorithm algorithm = UnknownAlgorithm;

	bool busy = FALSE;
	message_t packet;

	event void Boot.booted()
	{
		dbg("Boot", "%s: Application booted.\n", sim_time_string());

		sequence_number_init(&normal_sequence_counter);
		sequence_number_init(&away_sequence_counter);
		sequence_number_init(&choose_sequence_counter);
		sequence_number_init(&fake_sequence_counter);

		if (TOS_NODE_ID == SOURCE_NODE_ID)
		{
			type = SourceNode;
		}
		else if (TOS_NODE_ID == SINK_NODE_ID)
		{
			type = SinkNode;
		}

		call RadioControl.start();
	}

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			dbg("SourceBroadcasterC", "%s: RadioControl started.\n", sim_time_string());

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
		dbg("SourceBroadcasterC", "%s: RadioControl stopped.\n", sim_time_string());
	}

	SEND_DONE(Normal);
	SEND_DONE(Away);
	SEND_DONE(Choose);
	SEND_DONE(Fake);

	SEND_MESSAGE(Normal);
	SEND_MESSAGE(Away);
	SEND_MESSAGE(Choose);
	SEND_MESSAGE(Fake);

	void become_Normal()
	{
		type = NormalNode;
	}

	void become_Fake(bool perm, uint32_t duration)
	{
		type = perm ? PermFakeNode : TempFakeNode;
	}

	event void BroadcastNormalTimer.fired()
	{
		NormalMessage message;

		dbg("SourceBroadcasterC", "%s: BroadcastNormalTimer fired.\n", sim_time_string());

		message.sequence_number = sequence_number_next(&normal_sequence_counter);
		message.hop = 0;
		message.source_id = TOS_NODE_ID;

		if (send_Normal_message(&message))
		{
			sequence_number_increment(&normal_sequence_counter);
		}
	}

	void Normal_receieve_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		NormalMessage forwarding_message;

		if (first_source_distance == BOTTOM || rcvd->max_hop - 1 > first_source_distance)
		{
			is_pfs_candidate = FALSE;
		}

		sink_source_distance = minbot(sink_source_distance, (int32_t)rcvd->sink_source_distance);

		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			dbg_clear("Metric-RCV-Normal", "%" PRIu64 ",%u,%u,%u\n", sim_time(), TOS_NODE_ID, source_addr, rcvd->sequence_number);

			dbg("SourceBroadcasterC", "%s: Received unseen Normal seqno=%u from %u.\n", sim_time_string(), rcvd->sequence_number, source_addr);

			if (first_source_distance == BOTTOM)
			{
				first_source_distance = rcvd->hop + 1;
				is_pfs_candidate = TRUE;
			}

			source_distance = minbot(source_distance, (int32_t)rcvd->hop + 1);

			forwarding_message = *rcvd;
			forwarding_message.hop += 1;
			forwarding_message.max_hop = max(first_source_distance, (int32_t)rcvd->max_hop);

			send_Normal_message(&forwarding_message);
		}
		/*else
		{
			dbg("SourceBroadcasterC", "%s: Received previously seen Normal seqno=%u.\n", sim_time_string(), rcvd->sequence_number);
		}*/
	}

	void Sink_receieve_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			dbg_clear("Metric-RCV-Normal", "%" PRIu64 ",%u,%u,%u\n", sim_time(), TOS_NODE_ID, source_addr, rcvd->sequence_number);

			sink_source_distance = minbot(sink_source_distance, rcvd->hop + 1);

			if (!sink_sent_away)
			{
				AwayMessage message;
				message.sequence_number = sequence_number_next(&away_sequence_counter);
				message.sink_distance = 0;
				message.sink_source_distance = sink_source_distance;
				message.max_hop = first_source_distance;

				sequence_number_increment(&away_sequence_counter);

				sink_sent_away = TRUE;

				// TODO sense repeat 3 in (Psource / 2)
				send_Away_message(&message);
			}
		}
	}

	void Fake_receieve_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		NormalMessage forwarding_message;

		sink_source_distance = minbot(sink_source_distance, (int32_t)rcvd->sink_source_distance);

		if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			dbg_clear("Metric-RCV-Normal", "%" PRIu64 ",%u,%u,%u\n", sim_time(), TOS_NODE_ID, source_addr, rcvd->sequence_number);

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.hop += 1;
			forwarding_message.max_hop = max(first_source_distance, (int32_t)rcvd->max_hop);

			send_Normal_message(&forwarding_message);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal)
		case SinkNode: Sink_receieve_Normal(rcvd, source_addr); break;
		case NormalNode: Normal_receieve_Normal(rcvd, source_addr); break;
		case TempFakeNode:
		case PermFakeNode:
			Fake_receieve_Normal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)


	void Source_receieve_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		AwayMessage forwarding_message;

		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_source_distance = minbot(sink_source_distance, (int32_t)rcvd->sink_source_distance);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			dbg_clear("Metric-RCV-Away", "%" PRIu64 ",%u,%u,%u\n", sim_time(), TOS_NODE_ID, source_addr, rcvd->sequence_number);

			sink_source_distance = minbot(sink_source_distance, (int32_t)rcvd->sink_distance + 1);

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;

			send_Away_message(&forwarding_message);
		}
	}

	void Normal_receieve_Away(const AwayMessage* const rcvd, am_addr_t source_addr)
	{
		AwayMessage forwarding_message;

		if (first_source_distance == BOTTOM || rcvd->max_hop - 1 > first_source_distance)
		{
			is_pfs_candidate = FALSE;
		}

		if (algorithm == UnknownAlgorithm)
		{
			algorithm = (Algorithm)rcvd->algorithm;
		}

		sink_source_distance = minbot(sink_source_distance, (int32_t)rcvd->sink_source_distance);

		if (sequence_number_before(&away_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&away_sequence_counter, rcvd->sequence_number);

			dbg_clear("Metric-RCV-Away", "%" PRIu64 ",%u,%u,%u\n", sim_time(), TOS_NODE_ID, source_addr, rcvd->sequence_number);

			sink_distance = minbot(sink_distance, (int32_t)rcvd->sink_distance + 1);

			if (rcvd->sink_distance == 0)
			{
				become_Fake(TempFakeNode, TEMP_FAKE_DURATION);

				sequence_number_increment(&choose_sequence_counter);
			}

			forwarding_message = *rcvd;
			forwarding_message.sink_source_distance = sink_source_distance;
			forwarding_message.sink_distance += 1;
			forwarding_message.algorithm = algorithm;

			send_Away_message(&forwarding_message);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Away)
		case SourceNode: Source_receieve_Away(rcvd, source_addr); break;
		case NormalNode: Normal_receieve_Away(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Away)


	void Normal_receieve_Choose(const ChooseMessage* const rcvd, am_addr_t source_addr)
	{
		if (sequence_number_before(&choose_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&choose_sequence_counter, rcvd->sequence_number);

			dbg_clear("Metric-RCV-Choose", "%" PRIu64 ",%u,%u,%u\n", sim_time(), TOS_NODE_ID, source_addr, rcvd->sequence_number);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Choose)
		case NormalNode: Normal_receieve_Choose(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Choose)



	void Sink_receieve_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		sink_source_distance = minbot(sink_source_distance, (int32_t)rcvd->sink_source_distance);

		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			FakeMessage message = *rcvd;

			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			dbg_clear("Metric-RCV-Fake", "%" PRIu64 ",%u,%u,%u\n", sim_time(), TOS_NODE_ID, source_addr, rcvd->sequence_number);

			message.sink_source_distance = sink_source_distance;

			send_Fake_message(&message);
		}
	}

	void Source_receieve_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			dbg_clear("Metric-RCV-Fake", "%" PRIu64 ",%u,%u,%u\n", sim_time(), TOS_NODE_ID, source_addr, rcvd->sequence_number);
		}
	}

	void Normal_receieve_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			dbg_clear("Metric-RCV-Fake", "%" PRIu64 ",%u,%u,%u\n", sim_time(), TOS_NODE_ID, source_addr, rcvd->sequence_number);
		}
	}

	void Fake_receieve_Fake(const FakeMessage* const rcvd, am_addr_t source_addr)
	{
		if (sequence_number_before(&fake_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&fake_sequence_counter, rcvd->sequence_number);

			dbg_clear("Metric-RCV-Fake", "%" PRIu64 ",%u,%u,%u\n", sim_time(), TOS_NODE_ID, source_addr, rcvd->sequence_number);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Fake)
		case SinkNode: Sink_receieve_Fake(rcvd, source_addr); break;
		case SourceNode: Source_receieve_Fake(rcvd, source_addr); break;
		case NormalNode: Normal_receieve_Fake(rcvd, source_addr); break;
		case TempFakeNode:
		case PermFakeNode:
			Fake_receieve_Fake(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Fake)
}
