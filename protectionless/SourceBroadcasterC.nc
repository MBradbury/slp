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
	SequenceNumber normal_sequence_counter;

	bool busy = FALSE;
	message_t packet;

	void setLeds(uint32_t val)
	{
		if (val & 0x01)
		  call Leds.led0On();
		else 
		  call Leds.led0Off();

		if (val & 0x02)
		  call Leds.led1On();
		else
		  call Leds.led1Off();

		if (val & 0x04)
		  call Leds.led2On();
		else
		  call Leds.led2Off();
	}

	bool is_source_node()
	{
		return TOS_NODE_ID == 1;
	}

	event void Boot.booted()
	{
		dbg("Boot", "%s: Application booted.\n", sim_time_string());

		sequence_number_init(&normal_sequence_counter);

		call RadioControl.start();
	}

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			dbg("SourceBroadcasterC", "%s: RadioControl started.\n", sim_time_string());

			// TODO: replace this with some other way to identify the source node
			if (is_source_node())
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

	void generate_and_send_normal_message()
	{
		error_t status;

		if (!busy)
		{
			NormalMessage* const message = (NormalMessage*)(call Packet.getPayload(&packet, sizeof(NormalMessage)));
			if (message == NULL)
			{
				dbgerror("SourceBroadcasterC", "%s: Packet has no payload, or payload is too large.\n", sim_time_string());
				return;
			}

			message->sequence_number = sequence_number_get(&normal_sequence_counter);
			message->sink_source_distance = 0;
			message->hop = 0;
			message->max_hop = 0;
			message->source_id = TOS_NODE_ID;

			status = call NormalSend.send(AM_BROADCAST_ADDR, &packet, sizeof(NormalMessage));
			if (status == SUCCESS)
			{
				busy = TRUE;

				sequence_number_increment(&normal_sequence_counter);
			}
		}
		else
		{
			dbg("SourceBroadcasterC", "%s: BroadcastNormalTimer busy, not sending Normal message.\n", sim_time_string());
		}
	}

	event void BroadcastNormalTimer.fired()
	{
		dbg("SourceBroadcasterC", "%s: BroadcastNormalTimer fired.\n", sim_time_string());

		generate_and_send_normal_message();
	}

	event void NormalSend.sendDone(message_t* msg, error_t error)
	{
		dbg("SourceBroadcasterC", "%s: NormalSend sendDone with status %i.\n", sim_time_string(), error);

		if (&packet == msg)
		{
			busy = FALSE;
		}
	}

	bool forward_normal_message(const NormalMessage* normal_rcvd)
	{
		error_t status;

		if (!busy)
		{
			NormalMessage* forwarding_message = (NormalMessage*)(call Packet.getPayload(&packet, sizeof(NormalMessage)));
			if (forwarding_message == NULL)
			{
				dbgerror("SourceBroadcasterC", "%s: Packet has no payload, or payload is too large.\n", sim_time_string());
				return FALSE;
			}

			*forwarding_message = *normal_rcvd;
			forwarding_message->hop += 1;

			status = call NormalSend.send(AM_BROADCAST_ADDR, &packet, sizeof(NormalMessage));
			if (status == SUCCESS)
			{
				busy = TRUE;
			}

			return TRUE;
		}
		else
		{
			dbgerror("SourceBroadcasterC", "%s: BroadcastNormal busy, not forwarding Normal message.\n", sim_time_string());
			return FALSE;
		}
	}

	event message_t* NormalReceive.receive(message_t* msg, void* payload, uint8_t len)
	{
		const NormalMessage* const normal_rcvd = (const NormalMessage*)payload;
		am_addr_t source_addr;

		if (len != sizeof(NormalMessage))
		{
			dbgerror("SourceBroadcasterC", "%s: Received Normal of invalid length %hhu.\n", sim_time_string(), len);
			return msg;
		}

		dbg("SourceBroadcasterC", "%s: Received valid Normal.\n", sim_time_string());

		source_addr = call AMPacket.source(msg);

		setLeds(normal_rcvd->sequence_number);

		if (sequence_number_before(&normal_sequence_counter, normal_rcvd->sequence_number))
		{
			sequence_number_update(&normal_sequence_counter, normal_rcvd->sequence_number);

			dbg("SourceBroadcasterC", "%s: Received unseen Normal seqno=%u from %u.\n", sim_time_string(), normal_rcvd->sequence_number, source_addr);

			forward_normal_message(normal_rcvd);
		}
		/*else
		{
			dbg("SourceBroadcasterC", "%s: Received previously seen Normal seqno=%u.\n", sim_time_string(), normal_msg->sequence_number);
		}*/

		return msg;
	}
}
