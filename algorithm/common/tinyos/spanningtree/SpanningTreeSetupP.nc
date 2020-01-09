
// Spanning Tree Implementation (UDG-NNT) from Khan:2009:DistributedAlgorithmsConstructing sec. 4.1

#include "Common.h"

#include "ConnectMessage.h"
#include "SetupMessage.h"

#define METRIC_RCV_CONNECT(msg) METRIC_RCV(Connect, msg->proximate_source_id, msg->proximate_source_id, UNKNOWN_SEQNO, 1)
#define METRIC_RCV_SETUP(msg) METRIC_RCV(Setup, msg->proximate_source_id, msg->proximate_source_id, UNKNOWN_SEQNO, 1)

module SpanningTreeSetupP
{
	provides interface StdControl;

	uses {
		interface SpanningTreeInfo as Info;
		interface RootControl;

		interface Random;

		interface AMSend as SetupSend;
		interface Receive as SetupReceive;

		interface AMSend as ConnectSend;
		interface Receive as ConnectReceive;
		interface Receive as ConnectSnoop;

		interface AMSend as RoutingSend;

		interface AMPacket;

		interface PacketAcknowledgements;
		interface LinkEstimator;

		interface Timer<TMilli> as SetupTimer;
		interface Timer<TMilli> as ConnectTimer;

		interface MetricLogging;

		interface Dictionary<am_addr_t, uint16_t> as NeighbourRootDistances;
		interface Set<am_addr_t> as Connections;
	}
}
implementation
{
	bool busy = FALSE;
	message_t packet;

	uint32_t setup_period;

	uint16_t root_distance;
	bool root_distance_set = FALSE;

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

	am_addr_t find_link(void)
	{
		am_addr_t chosen_neighbour = TOS_NODE_ID;
		uint16_t chosen_dist = root_distance;
		uint16_t chosen_link_quality = UINT16_MAX;

		const am_addr_t* iter;
		const am_addr_t* end;

		if (!root_distance_set)
		{
			return AM_BROADCAST_ADDR;
		}

		for (iter = call NeighbourRootDistances.beginKeys(), end = call NeighbourRootDistances.endKeys(); iter != end; ++iter)
		{
			const uint16_t* neighbour_root_dist = call NeighbourRootDistances.get_from_iter(iter);

			uint16_t link_quality;

			if (neighbour_root_dist == NULL)
			{
				continue;
			}

			link_quality = call LinkEstimator.getForwardQuality(*iter);

			if ((*neighbour_root_dist < chosen_dist  && link_quality <= chosen_link_quality) ||
				(*neighbour_root_dist == chosen_dist && link_quality <  chosen_link_quality) ||
				(*neighbour_root_dist == chosen_dist && link_quality == chosen_link_quality && *iter < chosen_neighbour))
			{
				chosen_neighbour = *iter;
				chosen_dist = *neighbour_root_dist;
				chosen_link_quality = link_quality;
			}
		}

		if (chosen_neighbour == TOS_NODE_ID)
		{
			return AM_BROADCAST_ADDR;
		}

		return chosen_neighbour;
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

		if (message == NULL)
		{
			return;
		}

		message->proximate_source_id = TOS_NODE_ID;
		message->root_distance = root_distance;
		message->sender_is_root = call RootControl.isRoot();

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
			call ConnectTimer.startOneShot(85);
			return;
		}

		if (call Info.get_parent() == AM_BROADCAST_ADDR)
		{
			return;
		}

		message = (ConnectMessage*)call ConnectSend.getPayload(&packet, sizeof(ConnectMessage));

		if (message == NULL)
		{
			return;
		}

		message->ack_requested = (call PacketAcknowledgements.requestAck(&packet) == SUCCESS);

		message->proximate_source_id = TOS_NODE_ID;
		message->root_distance = root_distance;

		status = call ConnectSend.send(call Info.get_parent(), &packet, sizeof(ConnectMessage));
		if (status == SUCCESS)
		{
			busy = TRUE;
		}
		else
		{
			call ConnectTimer.startOneShot(85);
		}
	}

	task void update_parent()
	{
		const am_addr_t new_parent = find_link();
		const am_addr_t current_parent = call Info.get_parent();

		if (new_parent != current_parent)
		{
			simdbg("G-A", "arrow,-,%u,%u,(0,0,0)\n", TOS_NODE_ID, current_parent);

			// Select the node which an edge exists
			call Info.set_parent(new_parent);

			simdbg("G-A", "arrow,+,%u,%u,(0,0,0)\n", TOS_NODE_ID, new_parent);

			post send_connect();
		}
	}

	command error_t StdControl.start()
	{
		setup_period = 2 * 1000;

		if (call RootControl.isRoot())
		{
			root_distance = 0;
			root_distance_set = TRUE;

			post send_setup();
		}
		else
		{
			root_distance = UINT16_MAX;
		}

		return SUCCESS;
	}

	command error_t StdControl.stop()
	{
		call ConnectTimer.stop();
		call SetupTimer.stop();

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
		const SetupMessage* rcvd = (SetupMessage*)payload;
		const am_addr_t from = call AMPacket.source(msg);

		METRIC_RCV_SETUP(rcvd);

		if (rcvd->sender_is_root)
		{
			call LinkEstimator.insertNeighbor(from);
            call LinkEstimator.pinNeighbor(from);
		}

		if (!root_distance_set || root_distance > (rcvd->root_distance + 1))
		{
			root_distance = rcvd->root_distance + 1;
			root_distance_set = TRUE;

			decrease_setup_period();

			post send_setup();
		}
		else
		{
			increase_setup_period();
		}

		call NeighbourRootDistances.put(rcvd->proximate_source_id, rcvd->root_distance);

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

		// If we received a connect, then the sender has chosen us as its parent.

		call Connections.put(rcvd->proximate_source_id);

		return msg;
	}

	event message_t* ConnectSnoop.receive(message_t* msg, void* payload, uint8_t len)
	{
		ConnectMessage* rcvd = (ConnectMessage*)payload;

		METRIC_RCV_CONNECT(rcvd); // TODO: receive here?

		// If we snooped a connect, then the sender has chosen a new parent.

		call Connections.remove(rcvd->proximate_source_id);

		return msg;
	}

	event void SetupTimer.fired()
	{
		post send_setup();
	}

	event void ConnectTimer.fired()
	{
		post update_parent();
	}

	event void LinkEstimator.evicted(am_addr_t neighbour)
	{
		call NeighbourRootDistances.remove(neighbour);

		post update_parent();
	}

	event void RoutingSend.sendDone(message_t* msg, error_t error)
	{
		if (error == ENOACK)
		{
			post update_parent();
		}
	}
}
