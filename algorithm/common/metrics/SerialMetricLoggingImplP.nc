#include "MetricLogging.h"

#ifndef USE_SERIAL_MESSAGES
#	error "Must only use MetricLoggingP when USE_SERIAL_MESSAGES is defined"
#endif

//#define MAX_SERIAL_PACKET_SIZE 255

#define SERIAL_START_SEND(MESSAGE_NAME) \
	message_t* packet; \
	MESSAGE_NAME* msg; \
	error_t result; \
 \
	atomic { \
		packet = call MessagePool.get(); \
	} \
	/* Check if pool was full */ \
	if (packet == NULL) { \
		return; \
	} \
 \
 	call Packet.setPayloadLength(packet, sizeof(MESSAGE_NAME)); \
	msg = (MESSAGE_NAME*)call Packet.getPayload(packet, sizeof(MESSAGE_NAME)); \
 \
	/*STATIC_ASSERT_MSG(sizeof(MESSAGE_NAME) <= MAX_SERIAL_PACKET_SIZE, Need_to_increase_the_MAX_SERIAL_PACKET_SIZE_for_##MESSAGE_NAME);*/ \
 \
 	msg->node_id = TOS_NODE_ID; \
	msg->local_time = call LocalTime.get();

#define SERIAL_END_SEND(MESSAGE_NAME) \
	call AMPacket.setType(packet, msg->type); \
	atomic { \
		result = call MessageQueue.enqueue(packet); \
	} \
 \
	if (result != SUCCESS) \
	{ \
		/* Not really much that can be done here... */ \
	} \
	else \
	{ \
		post serial_sender(); \
	}

module SerialMetricLoggingImplP
{
	provides interface MetricLogging;

	provides interface Init;

	uses interface MessageType;

	uses interface LocalTime<TMilli>;

	uses interface SplitControl as SerialControl;
	uses interface Packet;
	uses interface AMPacket;

	uses interface AMSend as SerialSend[am_id_t id];

	uses interface Pool<message_t> as MessagePool;
	uses interface Queue<message_t*> as MessageQueue;
}
implementation
{
	bool locked;

	command error_t Init.init()
	{
		locked = FALSE;
		return SUCCESS;
	}

	event void SerialControl.startDone(error_t err)
	{
		if (err != SUCCESS)
		{
			call SerialControl.start();
		}
	}

	event void SerialControl.stopDone(error_t err)
	{
	}

	task void serial_sender()
	{
		message_t* packet;
		error_t result;

		atomic {
			if (call MessageQueue.empty())
			{
				return;
			}

			if (locked)
			{
				return;
			}

			locked = TRUE;

			packet = call MessageQueue.element(0);
		}

		result = call SerialSend.send[call AMPacket.type(packet)](AM_BROADCAST_ADDR, packet, call Packet.payloadLength(packet));

		// If we failed to send, then unlock
		if (result != SUCCESS)
		{
			atomic {
				locked = FALSE;
			}
		}
	}

	event void SerialSend.sendDone[am_id_t am_id](message_t* msg, error_t error)
	{
		atomic {
			locked = FALSE;
			if (error == SUCCESS)
			{
				// Remove the sent message from the queue
				call MessageQueue.dequeue();

				// Return message to pool
				call MessagePool.put(msg);

				// If there are more messages to send then send them
				if (!call MessageQueue.empty())
				{
					post serial_sender();
				}
			}
			else
			{
				// Retry sending the message
				post serial_sender();
			}
		}
	}

	command void MetricLogging.log_metric_receive(
		const char* message_type,
		am_addr_t proximate_source,
		am_addr_t ultimate_source,
		SequenceNumberWithBottom sequence_number,
		int16_t distance
		)
	{
		SERIAL_START_SEND(metric_receive_msg_t)

		msg->type = AM_METRIC_RECEIVE_MSG;

		msg->message_type = call MessageType.from_string(message_type);
		msg->proximate_source = proximate_source;
		msg->ultimate_source = ultimate_source;
		msg->sequence_number = sequence_number;
		msg->distance = distance;

		SERIAL_END_SEND(metric_receive_msg_t)
	}

	command void MetricLogging.log_metric_bcast(
		const char* message_type,
		error_t status,
		SequenceNumberWithBottom sequence_number
		)
	{
		SERIAL_START_SEND(metric_bcast_msg_t)

		msg->type = AM_METRIC_BCAST_MSG;

		msg->message_type = call MessageType.from_string(message_type);
		msg->status = status;
		msg->sequence_number = sequence_number;

		SERIAL_END_SEND(metric_bcast_msg_t)
	}

	command void MetricLogging.log_metric_deliver(
		const char* message_type,
		am_addr_t proximate_source,
		int32_t ultimate_source_poss_bottom,
		SequenceNumberWithBottom sequence_number
		)
	{
		SERIAL_START_SEND(metric_deliver_msg_t)

		msg->type = AM_METRIC_DELIVER_MSG;

		msg->message_type = call MessageType.from_string(message_type);
		msg->proximate_source = proximate_source;
		msg->ultimate_source_poss_bottom = ultimate_source_poss_bottom;
		msg->sequence_number = sequence_number;

		SERIAL_END_SEND(metric_deliver_msg_t)
	}

	command void MetricLogging.log_attacker_receive(
		const char* message_type,
		const message_t* wsn_msg,
		am_addr_t proximate_source,
		int32_t ultimate_source_poss_bottom,
		SequenceNumberWithBottom sequence_number
		)
	{
		SERIAL_START_SEND(attacker_receive_msg_t)

		msg->type = AM_ATTACKER_RECEIVE_MSG;

		msg->message_type = call MessageType.from_string(message_type);
		msg->proximate_source = proximate_source;
		msg->ultimate_source_poss_bottom = ultimate_source_poss_bottom;
		msg->sequence_number = sequence_number;

		SERIAL_END_SEND(attacker_receive_msg_t)
	}

	command void MetricLogging.log_metric_node_change(
		uint8_t old_type,
		const char* old_type_str,
		uint8_t new_type,
		const char* new_type_str
		)
	{
		SERIAL_START_SEND(metric_node_change_msg_t)

		msg->type = AM_METRIC_NODE_CHANGE_MSG;

		msg->old_node_type = old_type;
		msg->new_node_type = new_type;

		SERIAL_END_SEND(metric_node_change_msg_t)
	}

	command void MetricLogging.log_metric_node_type_add(
		uint8_t node_type_id,
		const char* node_type_name
		)
	{
		SERIAL_START_SEND(metric_node_type_add_msg_t)

		msg->type = AM_METRIC_NODE_TYPE_ADD_MSG;

		msg->node_type_id = node_type_id;

		strncpy((char*)msg->node_type_name, node_type_name, ARRAY_SIZE(msg->node_type_name));

		SERIAL_END_SEND(metric_node_type_add_msg_t)
	}

	command void MetricLogging.log_metric_message_type_add(
		uint8_t message_type_id,
		const char* message_type_name
		)
	{
		SERIAL_START_SEND(metric_message_type_add_msg_t)

		msg->type = AM_METRIC_MESSAGE_TYPE_ADD_MSG;

		msg->message_type_id = message_type_id;

		strncpy((char*)msg->message_type_name, message_type_name, ARRAY_SIZE(msg->message_type_name));

		SERIAL_END_SEND(metric_message_type_add_msg_t)
	}

    command void MetricLogging.log_metric_fault_point_type_add(
            uint8_t fault_point_id,
            const char* fault_point_name
            )
    {
        SERIAL_START_SEND(metric_fault_point_type_add_msg_t)

        msg->type = AM_METRIC_FAULT_POINT_TYPE_ADD_MSG;

        msg->fault_point_id = fault_point_id;

        strncpy((char*)msg->fault_point_name, fault_point_name, ARRAY_SIZE(msg->fault_point_name));

        SERIAL_END_SEND(metric_fault_point_type_add_msg_t)
    }

    command void MetricLogging.log_metric_fault_point(
            uint8_t fault_point_id
            )
    {
        SERIAL_START_SEND(metric_fault_point_msg_t)

        msg->type = AM_METRIC_FAULT_POINT_MSG;

        msg->fault_point_id = fault_point_id;

        SERIAL_END_SEND(metric_fault_point_msg_t)
    }

	command void MetricLogging.log_error_occurred(
		uint16_t code,
		const char* message
		)
	{
		SERIAL_START_SEND(error_occurred_msg_t)

		msg->type = AM_ERROR_OCCURRED_MSG;

		msg->error_code = code;

		SERIAL_END_SEND(error_occurred_msg_t)
	}

	command void MetricLogging.log_stdout(
		uint16_t code,
		const char* message
		)
	{
		SERIAL_START_SEND(event_occurred_msg_t)

		msg->type = AM_EVENT_OCCURRED_MSG;

		msg->event_code = code;

		SERIAL_END_SEND(event_occurred_msg_t)
	}

	//##########SLP TDMA DAS##########
	command void MetricLogging.log_metric_node_slot_change(
		uint16_t old_slot,
		uint16_t new_slot
		)
	{
		SERIAL_START_SEND(metric_node_slot_change_msg_t)

		msg->type = AM_METRIC_NODE_SLOT_CHANGE_MSG;
		
		msg->old_slot = old_slot;
		msg->new_slot = new_slot;

		SERIAL_END_SEND(metric_node_slot_change_msg_t)
	}

    command void MetricLogging.log_metric_start_period()
    {
        SERIAL_START_SEND(metric_start_period_msg_t)

        msg->type = AM_METRIC_START_PERIOD_MSG;

        SERIAL_END_SEND(metric_start_period_msg_t)
    }

	//##########Tree based routing##########
	command void MetricLogging.log_metric_parent_change(
		am_addr_t old_parent,
		am_addr_t new_parent
		)
	{
		SERIAL_START_SEND(metric_parent_change_msg_t)

		msg->type = AM_METRIC_PARENT_CHANGE_MSG;
		
		msg->old_parent = old_parent;
		msg->new_parent = new_parent;

		SERIAL_END_SEND(metric_parent_change_msg_t)
	}
}
