#include "MetricLogging.h"

#ifndef USE_SERIAL_MESSAGES
#	error "Must only use MetricLoggingP when USE_SERIAL_MESSAGES is defined"
#endif

#define MAX_SERIAL_PACKET_SIZE 255

#define SERIAL_START_SEND(SENDER_NAME, MESSAGE_NAME) \
	MESSAGE_NAME* msg = (MESSAGE_NAME*)call Packet.getPayload(&packet, sizeof(MESSAGE_NAME)); \
 \
	STATIC_ASSERT_MSG(sizeof(MESSAGE_NAME) <= MAX_SERIAL_PACKET_SIZE, Need_to_increase_the_MAX_SERIAL_PACKET_SIZE_for_##MESSAGE_NAME); \
 \
 	msg->node_id = TOS_NODE_ID; \
	msg->local_time = call LocalTime.get(); \

#define SERIAL_END_SEND(SENDER_NAME, MESSAGE_NAME) \
	if (locked) \
	{ \
		/* If locked then just add this message to the queue */ \
		message_t* pool_packet = call MessagePool.get(); \
		memcpy(pool_packet, &packet, sizeof(*pool_packet)); \
		if (call MessageQueue.enqueue(pool_packet) != SUCCESS) \
		{ \
		} \
	} \
	else \
	{ \
		/* Try to send the message */ \
		if (call SENDER_NAME.send(AM_BROADCAST_ADDR, &packet, sizeof(MESSAGE_NAME)) == SUCCESS) \
		{ \
			locked = TRUE; \
		} \
		else \
		{ \
			/* Add the message to the queue on failure */ \
			message_t* pool_packet = call MessagePool.get(); \
			memcpy(pool_packet, &packet, sizeof(*pool_packet)); \
			if (call MessageQueue.enqueue(pool_packet) != SUCCESS) \
			{ \
			} \
		} \
	}
	

#define SERIAL_SEND_DONE(SENDER_NAME) \
	event void SENDER_NAME.sendDone(message_t* msg, error_t error) \
	{ \
		if (msg == &packet) \
		{ \
			locked = FALSE; \
		} \
		else \
		{ \
			locked = FALSE; \
			/* Return message to pool, if memory originated from pool */ \
			call MessagePool.put(msg); \
		} \
 \
		if (error != SUCCESS) \
		{ \
			/* TODO */ \
		} \
	}


module SerialMetricLoggingImplP
{
	provides interface MetricLogging;

	uses interface LocalTime<TMilli>;

	uses interface SplitControl as SerialControl;
	uses interface Packet;
	uses interface AMPacket;

	uses interface AMSend as MetricReceiveSend;
	uses interface AMSend as MetricBcastSend;
	uses interface AMSend as MetricDeliverSend;
	uses interface AMSend as AttackerReceiveSend;
	uses interface AMSend as MetricNodeChangeSend;

	uses interface Pool<message_t> as MessagePool;
	uses interface Queue<message_t*> as MessageQueue;
}
implementation
{
	message_t packet;
	bool locked = FALSE;

	uint8_t message_type_string_to_int(const char* message_type)
	{
		if (strcmp(message_type, "Normal") == 0)
		{
			return 1;
		}
		else
		{
			// 0 is unknown
			return 0;
		}
	}

	event void SerialControl.startDone(error_t err)
	{

	}

	event void SerialControl.stopDone(error_t err)
	{
		
	}

	SERIAL_SEND_DONE(MetricReceiveSend)
	SERIAL_SEND_DONE(MetricBcastSend)
	SERIAL_SEND_DONE(MetricDeliverSend)
	SERIAL_SEND_DONE(AttackerReceiveSend)
	SERIAL_SEND_DONE(MetricNodeChangeSend)

	command void MetricLogging.log_metric_receive(
		const char* message_type,
		am_addr_t proximate_source,
		am_addr_t ultimate_source,
		SequenceNumberWithBottom sequence_number,
		int16_t distance
		)
	{
		SERIAL_START_SEND(MetricReceiveSend, metric_receive_msg_t)

		msg->type = AM_METRIC_RECEIVE_MSG;

		msg->message_type = message_type_string_to_int(message_type);
		msg->proximate_source = proximate_source;
		msg->ultimate_source = ultimate_source;
		msg->sequence_number = sequence_number;
		msg->distance = distance;

		SERIAL_END_SEND(MetricReceiveSend, metric_receive_msg_t)
	}

	command void MetricLogging.log_metric_bcast(
		const char* message_type,
		error_t status,
		SequenceNumberWithBottom sequence_number
		)
	{
		SERIAL_START_SEND(MetricBcastSend, metric_bcast_msg_t)

		msg->type = AM_METRIC_BCAST_MSG;

		msg->message_type = message_type_string_to_int(message_type);
		msg->status = status;
		msg->sequence_number = sequence_number;

		SERIAL_END_SEND(MetricBcastSend, metric_bcast_msg_t)
	}

	command void MetricLogging.log_metric_deliver(
		const char* message_type,
		am_addr_t proximate_source,
		int32_t ultimate_source_poss_bottom,
		SequenceNumberWithBottom sequence_number
		)
	{
		SERIAL_START_SEND(MetricDeliverSend, metric_deliver_msg_t)

		msg->type = AM_METRIC_DELIVER_MSG;

		msg->message_type = message_type_string_to_int(message_type);
		msg->proximate_source = proximate_source;
		msg->ultimate_source_poss_bottom = ultimate_source_poss_bottom;
		msg->sequence_number = sequence_number;

		SERIAL_END_SEND(MetricDeliverSend, metric_deliver_msg_t)
	}

	command void MetricLogging.log_attacker_receive(
		const char* message_type,
		am_addr_t proximate_source,
		int32_t ultimate_source_poss_bottom,
		SequenceNumberWithBottom sequence_number
		)
	{
		SERIAL_START_SEND(AttackerReceiveSend, attacker_receive_msg_t)

		msg->type = AM_ATTACKER_RECEIVE_MSG;

		msg->message_type = message_type_string_to_int(message_type);
		msg->proximate_source = proximate_source;
		msg->ultimate_source_poss_bottom = ultimate_source_poss_bottom;
		msg->sequence_number = sequence_number;

		SERIAL_END_SEND(AttackerReceiveSend, attacker_receive_msg_t)
	}

	command void MetricLogging.log_metric_node_change(
		uint8_t old_type,
		const char* old_type_str,
		uint8_t new_type,
		const char* new_type_str
		)
	{
		SERIAL_START_SEND(MetricNodeChangeSend, metric_node_change_msg_t)

		msg->type = AM_METRIC_NODE_CHANGE_MSG;

		msg->old_message_type = old_type;
		msg->new_message_type = new_type;

		SERIAL_END_SEND(MetricNodeChangeSend, metric_node_change_msg_t)
	}

	command void MetricLogging.log_error_occurred(
		uint16_t code,
		const char* message
		)
	{
	}
}
