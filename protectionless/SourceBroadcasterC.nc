#include "Constants.h"
#include "NormalMessage.h"
#include "SequenceNumber.h"

#include <Timer.h>
#include <TinyError.h>

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
		SourceNode, SinkNode, PermFakeSourceNode, TempFakeSourceNode, NormalNode
	} NodeType;

	NodeType type = NormalNode;

	const char* type_to_string()
	{
		switch (type)
		{
		case SourceNode: 			return "SourceNode";
		case SinkNode:				return "SinkNode  ";
		case PermFakeSourceNode:	return "PermFS    ";
		case TempFakeSourceNode:	return "TempFS    ";
		case NormalNode:			return "NormalNode";
		default:					return "<unknown> ";
		}
	}

	SequenceNumber normal_sequence_counter;

	bool busy = FALSE;
	message_t packet;

	event void Boot.booted()
	{
		dbg("Boot", "%s: Application booted.\n", sim_time_string());

		sequence_number_init(&normal_sequence_counter);

		if (TOS_NODE_ID == 0)
		{
			type = SourceNode;
		}
		if (TOS_NODE_ID == 60)
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

	bool send_normal_message(const NormalMessage* tosend)
	{
		error_t status;

		if (!busy)
		{
			NormalMessage* const message = (NormalMessage*)(call Packet.getPayload(&packet, sizeof(NormalMessage)));
			if (message == NULL)
			{
				dbgerror("SourceBroadcasterC", "%s: Packet has no payload, or payload is too large.\n", sim_time_string());
				return FALSE;
			}

			*message = *tosend;

			status = call NormalSend.send(AM_BROADCAST_ADDR, &packet, sizeof(NormalMessage));
			if (status == SUCCESS)
			{
				call Leds.led0On();
				busy = TRUE;

				dbg_clear("Metric-BCAST-Normal", "%" PRIu64 ",%u,%s,%u\n", sim_time(), TOS_NODE_ID, "success", tosend->sequence_number);

				return TRUE;
			}
			else
			{
				dbg_clear("Metric-BCAST-Normal", "%" PRIu64 ",%u,%s,%u\n", sim_time(), TOS_NODE_ID, "failed", tosend->sequence_number);

				return FALSE;
			}
		}
		else
		{
			dbg("SourceBroadcasterC", "%s: BroadcastNormalTimer busy, not sending Normal message.\n", sim_time_string());

			dbg_clear("Metric-BCAST-Normal", "%" PRIu64 ",%u,%s,%u\n", sim_time(), TOS_NODE_ID, "busy", tosend->sequence_number);

			return FALSE;
		}
	}

	event void BroadcastNormalTimer.fired()
	{
		NormalMessage message;

		dbg("SourceBroadcasterC", "%s: BroadcastNormalTimer fired.\n", sim_time_string());

		message.sequence_number = sequence_number_next(&normal_sequence_counter);
		message.hop = 0;
		message.source_id = TOS_NODE_ID;

		if (send_normal_message(&message))
		{
			sequence_number_increment(&normal_sequence_counter);
		}
	}

	event void NormalSend.sendDone(message_t* msg, error_t error)
	{
		dbg("SourceBroadcasterC", "%s: NormalSend sendDone with status %i.\n", sim_time_string(), error);

		if (&packet == msg)
		{
			call Leds.led0Off();
			busy = FALSE;
		}
	}

	void Normal_receieve_Normal(message_t* msg, const NormalMessage* const normal_rcvd)
	{
		NormalMessage forwarding_message;
		const am_addr_t source_addr  = call AMPacket.source(msg);

		if (sequence_number_before(&normal_sequence_counter, normal_rcvd->sequence_number))
		{
			sequence_number_update(&normal_sequence_counter, normal_rcvd->sequence_number);

			dbg_clear("Metric-RCV-Normal", "%" PRIu64 ",%u,%u,%u\n", sim_time(), TOS_NODE_ID, source_addr, normal_rcvd->sequence_number);

			dbg("SourceBroadcasterC", "%s: Received unseen Normal seqno=%u from %u.\n", sim_time_string(), normal_rcvd->sequence_number, source_addr);

			forwarding_message = *normal_rcvd;
			forwarding_message.hop += 1;

			send_normal_message(&forwarding_message);
		}
		/*else
		{
			dbg("SourceBroadcasterC", "%s: Received previously seen Normal seqno=%u.\n", sim_time_string(), normal_rcvd->sequence_number);
		}*/
	}

	void Sink_receieve_Normal(message_t* msg, const NormalMessage* const normal_rcvd)
	{
		const am_addr_t source_addr = call AMPacket.source(msg);

		if (sequence_number_before(&normal_sequence_counter, normal_rcvd->sequence_number))
		{
			sequence_number_update(&normal_sequence_counter, normal_rcvd->sequence_number);

			dbg_clear("Metric-RCV-Normal", "%" PRIu64 ",%u,%u,%u\n", sim_time(), TOS_NODE_ID, source_addr, normal_rcvd->sequence_number);
		}
	}

	event message_t* NormalReceive.receive(message_t* msg, void* payload, uint8_t len)
	{
		const NormalMessage* const normal_rcvd = (const NormalMessage*)payload;

		const am_addr_t source_addr = call AMPacket.source(msg);

		dbg_clear("Attacker-RCV", "%" PRIu64 ",%u,%u,%u,%u\n", sim_time(), "normal", TOS_NODE_ID, source_addr, normal_rcvd->sequence_number);

		if (len != sizeof(NormalMessage))
		{
			dbgerror("SourceBroadcasterC", "%s: Received Normal of invalid length %hhu.\n", sim_time_string(), len);
			return msg;
		}

		dbg("SourceBroadcasterC", "%s: Received valid Normal.\n", sim_time_string());

		switch (type)
		{
			case SinkNode: Sink_receieve_Normal(msg, normal_rcvd); break;

			case NormalNode: Normal_receieve_Normal(msg, normal_rcvd); break;

			default:
			{
				dbgerror("SourceBroadcasterC", "%s: Unknown node type %s. Cannot process Normal message\n", sim_time_string(), type_to_string());
			} break;
		}

		return msg;
	}
}
