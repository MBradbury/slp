
#include "Common.h"

module SpanningTreeRoutingP
{
	provides {
		interface Send[uint8_t client];
		interface Receive[uint8_t id];
		interface Receive as Snoop[uint8_t id];
		interface Intercept[uint8_t id];

		interface Packet;
	}

	uses {
		interface SpanningTreeInfo as Info;
		interface RootControl;

		interface AMSend as SubSend;
		interface Receive as SubReceive;
		interface Receive as SubSnoop;

		interface Packet as SubPacket;

		interface PacketAcknowledgements;
		interface Timer<TMilli> as RetransmitTimer;

		interface Queue<message_t*> as SendQueue;
		interface Pool<message_t> as MessagePool;
	}
}
implementation
{
	inline spanning_tree_data_header_t* get_packet_header(message_t* msg)
	{
		return (spanning_tree_data_header_t*)call SubPacket.getPayload(msg, sizeof(spanning_tree_data_header_t));
	}

	// Send / receive implementation

	void start_retransmit_timer()
	{
		call RetransmitTimer.startOneShot(1 * 1000);
	}

	task void send_message()
	{
		am_addr_t parent;
		message_t* msg;

		if (call SendQueue.empty())
		{
			return;
		}

		msg = call SendQueue.element(0);

		parent = call Info.get_parent();

		if (parent == AM_BROADCAST_ADDR)
		{
			return;
		}

		if (call SubSend.send(parent, msg, call SubPacket.payloadLength(msg)) != SUCCESS)
		{
			start_retransmit_timer();
		}
	}

	event void SubSend.sendDone(message_t* msg, error_t error)
	{
		if (error == SUCCESS)
		{
			call SendQueue.dequeue();

			if (call MessagePool.from(msg))
			{
				call MessagePool.put(msg);
			}
			else
			{
				spanning_tree_data_header_t* header = get_packet_header(msg);

				signal Send.sendDone[header->sub_id](msg, error);
			}
		}
		else
		{
			start_retransmit_timer();
		}
	}

	event message_t* SubReceive.receive(message_t* msg, void* payload, uint8_t len)
	{
		spanning_tree_data_header_t* header = get_packet_header(msg);
		uint8_t sub_len = call Packet.payloadLength(msg);
		void* sub_payload = call Packet.getPayload(msg, sub_len);

		if (call RootControl.isRoot())
		{
			signal Receive.receive[header->sub_id](msg, sub_payload, sub_len);
		}
		else
		{
			if (signal Intercept.forward[header->sub_id](msg, sub_payload, sub_len))
			{
				// Forward the message onwards
				message_t* new_message = call MessagePool.get();

				if (new_message == NULL)
				{
					// TODO: report error!
					return msg;
				}

				memcpy(new_message, msg, sizeof(message_t));

				if (call SendQueue.enqueue(new_message) == SUCCESS)
				{
					post send_message();
				}
				else
				{
					// TODO: report error!
					return msg;
				}
			}
		}

		return msg;
	}

	event message_t* SubSnoop.receive(message_t* msg, void* payload, uint8_t len)
	{
		spanning_tree_data_header_t* header = get_packet_header(msg);
		uint8_t sub_len = call Packet.payloadLength(msg);
		void* sub_payload = call Packet.getPayload(msg, sub_len);

		signal Snoop.receive[header->sub_id](msg, sub_payload, sub_len);

		return msg;
	}

	event void RetransmitTimer.fired()
	{
		post send_message();
	}

	// Packet implementation
	command void Packet.clear(message_t* msg)
	{
		call SubPacket.clear(msg);
	}

	command uint8_t Packet.payloadLength(message_t* msg)
	{
		return call SubPacket.payloadLength(msg) - sizeof(spanning_tree_data_header_t);
	}

	command void Packet.setPayloadLength(message_t* msg, uint8_t len)
	{
		call SubPacket.setPayloadLength(msg, len + sizeof(spanning_tree_data_header_t));
	}
  
	command uint8_t Packet.maxPayloadLength()
	{
		return call SubPacket.maxPayloadLength() - sizeof(spanning_tree_data_header_t);
	}

	command void* Packet.getPayload(message_t* msg, uint8_t len)
	{
		uint8_t* payload = call SubPacket.getPayload(msg, len + sizeof(spanning_tree_data_header_t));
		if (payload != NULL) {
			payload += sizeof(spanning_tree_data_header_t);
		}
		return payload;
	}

	// Send / Receive interface

	command error_t Send.send[uint8_t id](message_t* msg, uint8_t len)
	{
		spanning_tree_data_header_t* header;

		if (len > call Send.maxPayloadLength[id]())
			return ESIZE;

		call Packet.setPayloadLength(msg, len);

		header = get_packet_header(msg);
		header->sub_id = id;

		if (call SendQueue.enqueue(msg) == SUCCESS)
		{
			post send_message();

			return SUCCESS;
		}
		else
		{
			return ENOMEM;
		}
	}

	command error_t Send.cancel[uint8_t id](message_t* msg)
	{
		// cancel not implemented. will require being able
		// to pull entries out of the queue.
		return FAIL;
	}

	command uint8_t Send.maxPayloadLength[uint8_t id]()
	{
		return call Packet.maxPayloadLength();
	}

	command void* Send.getPayload[uint8_t client](message_t* msg, uint8_t len)
	{
		return call Packet.getPayload(msg, len);
	}


	// Default events

	default event void Send.sendDone[uint8_t client](message_t* msg, error_t error)
	{
	}

	default event bool Intercept.forward[uint8_t id](message_t* msg, void* payload, uint8_t len)
	{
		return TRUE;
	}

	default event message_t* Receive.receive[uint8_t id](message_t* msg, void* payload, uint8_t len)
	{
		return msg;
	}

	default event message_t* Snoop.receive[uint8_t id](message_t* msg, void* payload, uint8_t len)
	{
		return msg;
	}
}
