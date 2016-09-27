
// Spanning Tree Implementation (UDG-NNT) from Khan:2009:DistributedAlgorithmsConstructing sec. 4.1

#include "Common.h"

#include "ConnectMessage.h"
#include "SetupMessage.h"

#define METRIC_RCV_CONNECT(msg) METRIC_RCV(Connect, msg->proximate_source_id, BOTTOM, UNKNOWN_SEQNO, BOTTOM)
#define METRIC_RCV_SETUP(msg) METRIC_RCV(Setup, msg->proximate_source_id, BOTTOM, UNKNOWN_SEQNO, BOTTOM)

module SpanningTreeSetupP
{
	provides interface StdControl;

	uses interface SpanningTreeInfo as Info;

	uses interface Random;

	uses interface AMSend as SetupSend;
	uses interface Receive as SetupReceive;

	uses interface AMSend as ConnectSend;
	uses interface Receive as ConnectReceive;

	uses interface PacketAcknowledgements;

	uses interface Timer<TMilli> as SetupTimer;
	uses interface Timer<TMilli> as ConnectTimer;

	uses interface NodeType;
	uses interface MetricLogging;

	uses interface Dictionary<am_addr_t, uint16_t> as PDict;
	uses interface Set<am_addr_t> as Connections;
}
implementation
{
	bool busy = FALSE;
	message_t packet;

	uint32_t setup_period;

	uint16_t p;
	bool p_set = FALSE;

	int rank_comp(am_addr_t addr_v, uint16_t p_v, am_addr_t addr_w, uint16_t p_w)
	{
		if (p_v < p_w)
		{
			return -1;
		}
		else if (p_w == p_v)
		{
			if (addr_v < addr_w)
			{
				return -1;
			}
			else if (addr_v > addr_w)
			{
				return +1;
			}
			else
			{
				return 0;
			}
		}
		else
		{
			return +1;
		}
	}

	uint32_t decrease_setup_period()
	{
		setup_period /= 2;
		setup_period += call Random.rand16() % (1 * 1000);
		setup_period = max(setup_period, 1 * 1000);
		setup_period = min(setup_period, 1 * 60 * 1000);

		simdbgverbose("stdout", "Change - setup_period to %u\n", setup_period);

		return setup_period;
	}

	uint32_t increase_setup_period()
	{
		setup_period *= 2;
		setup_period += call Random.rand16() % (1 * 1000);
		setup_period = max(setup_period, 1 * 1000);
		setup_period = min(setup_period, 1 * 60 * 1000);

		simdbgverbose("stdout", "Change + setup_period to %u\n", setup_period);

		return setup_period;
	}

	task void send_setup()
	{
		error_t status;
		SetupMessage* message;

		if (busy)
		{
			call SetupTimer.startOneShot(decrease_setup_period());
			return;
		}

		message = (SetupMessage*)call SetupSend.getPayload(&packet, sizeof(SetupMessage));

		message->proximate_source_id = TOS_NODE_ID;
		message->p = p;

		status = call SetupSend.send(AM_BROADCAST_ADDR, &packet, sizeof(SetupMessage));
		if (status == SUCCESS)
		{
			busy = TRUE;
		}
		else
		{
			call SetupTimer.startOneShot(decrease_setup_period());
		}
	}

	task void send_connect()
	{
		error_t status;
		ConnectMessage* message;

		if (busy)
		{
			post send_connect();
			return;
		}

		if (call Info.get_parent() == AM_BROADCAST_ADDR)
		{
			return;
		}

		message = (ConnectMessage*)call ConnectSend.getPayload(&packet, sizeof(ConnectMessage));

		message->ack_requested = (call PacketAcknowledgements.requestAck(&packet) == SUCCESS);

		message->proximate_source_id = TOS_NODE_ID;
		message->p = p;

		status = call ConnectSend.send(call Info.get_parent(), &packet, sizeof(ConnectMessage));
		if (status == SUCCESS)
		{
			busy = TRUE;
		}
		else
		{
			post send_connect();
		}
	}

	command error_t StdControl.start()
	{
		setup_period = 2 * 1000;

		if (call NodeType.is_node_sink())
		{
			p = UINT16_MAX;
			p_set = TRUE;

			post send_setup();
		}

		return SUCCESS;
	}

	command error_t StdControl.stop()
	{
		return SUCCESS;
	}

	event void SetupSend.sendDone(message_t* msg, error_t error)
	{
		if (msg == &packet)
		{
			busy = FALSE;

			call SetupTimer.startOneShot(setup_period);
		}
	}

	event message_t* SetupReceive.receive(message_t* msg, void* payload, uint8_t len)
	{
		SetupMessage* rcvd = (SetupMessage*)payload;

		METRIC_RCV_SETUP(rcvd);

		// NOTE: the (p < rcvd->p - 1) check is my addition to
		// attempt to build a better route
		if (!p_set || p < (rcvd->p - 1))
		{
			p = rcvd->p - 1;
			p_set = TRUE;

			decrease_setup_period();

			post send_setup();
		}
		else
		{
			increase_setup_period();
		}

		call PDict.put(rcvd->proximate_source_id, rcvd->p);

		if (!call ConnectTimer.isRunning())
		{
			call ConnectTimer.startOneShot(5 * 1000);
		}

		return msg;
	}


	event void ConnectSend.sendDone(message_t* msg, error_t error)
	{
		const ConnectMessage* message = (ConnectMessage*)call ConnectSend.getPayload(msg, sizeof(ConnectMessage));

		if (msg == &packet)
		{
			busy = FALSE;
		}

		// Detect failures and retry
		if (error != SUCCESS)
		{
			post send_connect();
		}
		/*else if (message->ack_requested && !call PacketAcknowledgements.wasAcked(msg))
        {
            post send_connect();
        }*/
	}

	event message_t* ConnectReceive.receive(message_t* msg, void* payload, uint8_t len)
	{
		ConnectMessage* rcvd = (ConnectMessage*)payload;

		METRIC_RCV_CONNECT(rcvd);

		call Connections.put(rcvd->proximate_source_id);

		return msg;
	}

	am_addr_t find_link(void)
	{
		am_addr_t chosen_neighbour = AM_BROADCAST_ADDR;
		uint16_t chosen_p = UINT16_MAX;

		const am_addr_t* iter;
		const am_addr_t* end;

		if (!p_set)
		{
			return AM_BROADCAST_ADDR;
		}

		for (iter = call PDict.beginKeys(), end = call PDict.endKeys(); iter != end; ++iter)
		{
			const uint16_t* neighbour_p = call PDict.get_from_iter(iter);

			if (neighbour_p == NULL)
			{
				continue;
			}

			if (rank_comp(*iter, *neighbour_p, chosen_neighbour, chosen_p) < 0 &&
				rank_comp(TOS_NODE_ID, p, *iter, *neighbour_p) < 0)
			{
				chosen_neighbour = *iter;
				chosen_p = *neighbour_p;
			}
		}

		return chosen_neighbour;
	}

	event void SetupTimer.fired()
	{
		post send_setup();
	}

	event void ConnectTimer.fired()
	{
		simdbg("G-A", "arrow,-,%u,%u,(0,0,0)\n", TOS_NODE_ID, call Info.get_parent());

		// Select the node which an edge exists
		call Info.set_parent(find_link());

		simdbg("G-A", "arrow,+,%u,%u,(0,0,0)\n", TOS_NODE_ID, call Info.get_parent());

		post send_connect();
	}
}
