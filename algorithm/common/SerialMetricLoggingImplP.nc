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

	uses interface NodeType;

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
	bool locked = FALSE;

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

		msg->message_type = call NodeType.from_string(message_type);
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

		msg->message_type = call NodeType.from_string(message_type);
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

		msg->message_type = call NodeType.from_string(message_type);
		msg->proximate_source = proximate_source;
		msg->ultimate_source_poss_bottom = ultimate_source_poss_bottom;
		msg->sequence_number = sequence_number;

		SERIAL_END_SEND(metric_deliver_msg_t)
	}

	command void MetricLogging.log_attacker_receive(
		const char* message_type,
		am_addr_t proximate_source,
		int32_t ultimate_source_poss_bottom,
		SequenceNumberWithBottom sequence_number
		)
	{
		SERIAL_START_SEND(attacker_receive_msg_t)

		msg->type = AM_ATTACKER_RECEIVE_MSG;

		msg->message_type = call NodeType.from_string(message_type);
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

		msg->old_message_type = old_type;
		msg->new_message_type = new_type;

		SERIAL_END_SEND(metric_node_change_msg_t)
	}

	command void MetricLogging.log_metric_node_type_add(
		uint8_t node_type_id,
		const char* node_type_name
		)
	{
		SERIAL_START_SEND(metric_node_type_add_msg_t)

		msg->type = AM_METRIC_NODE_TYPE_ID_MSG;

		msg->node_type_id = node_type_id;

		strncpy((char*)msg->node_type_name, node_type_name, ARRAY_SIZE(msg->node_type_name));

		SERIAL_END_SEND(metric_node_type_add_msg_t)
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
}
