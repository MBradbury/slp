#ifndef SLP_SENDRECEIVEFUNCTIONS_H
#define SLP_SENDRECEIVEFUNCTIONS_H

// Include tos/types/message.h to get TOSH_DATA_LENGTH defined
#include "message.h"

#include "MetricLogging.h"

#include "pp.h"

#include <inttypes.h>

#define MSG_GET_NAME(TYPE, NAME) PPCAT(PPCAT(TYPE, _get_), NAME)
#define MSG_GET(TYPE, NAME, MSG) MSG_GET_NAME(TYPE, NAME)(MSG)

#define SEND_LED_ON call Leds.led0On()
#define SEND_LED_OFF call Leds.led0Off()

#define SEND_MESSAGE(NAME) \
error_t send_##NAME##_message_ex(const NAME##Message* tosend, am_addr_t target) \
{ \
	if (!busy || tosend == NULL) \
	{ \
		error_t status; \
 \
		void* const void_message = call NAME##Send.getPayload(&packet, sizeof(NAME##Message)); \
		NAME##Message* const message = (NAME##Message*)void_message; \
		if (message == NULL) \
		{ \
			ERROR_OCCURRED(ERROR_PACKET_HAS_NO_PAYLOAD, "Packet for " #NAME "Message has no payload.\n"); \
			return EINVAL; \
		} \
 \
		if (tosend != NULL) \
		{ \
			*message = *tosend; \
		} \
		else \
		{ \
			/* Need tosend set, so that the metrics recording works. */ \
			tosend = message; \
		} \
 \
		status = call NAME##Send.send(target, &packet, sizeof(NAME##Message)); \
		if (status == SUCCESS) \
		{ \
			SEND_LED_ON; \
			busy = TRUE; \
		} \
 \
		METRIC_BCAST(NAME, status, MSG_GET(NAME, sequence_number, tosend), call MetricHelpers.getTxPower(&packet)); \
 \
		return status; \
	} \
	else \
	{ \
		LOG_STDOUT_VERBOSE(EVENT_RADIO_BUSY, "Broadcast " #NAME " busy, not sending " #NAME " message.\n"); \
 \
		METRIC_BCAST(NAME, EBUSY, MSG_GET(NAME, sequence_number, tosend), call MetricHelpers.getTxPower(&packet)); \
 \
		return EBUSY; \
	} \
} \
inline bool send_##NAME##_message(const NAME##Message* tosend, am_addr_t target) \
{ \
	return send_##NAME##_message_ex(tosend, target) == SUCCESS; \
}

#define SEND_MESSAGE_ACK_REQUEST(NAME) \
error_t send_##NAME##_message_ex(const NAME##Message* tosend, am_addr_t target, bool* ack_request) \
{ \
	if (!busy || tosend == NULL) \
	{ \
		error_t status; \
 \
		void* const void_message = call NAME##Send.getPayload(&packet, sizeof(NAME##Message)); \
		NAME##Message* const message = (NAME##Message*)void_message; \
		if (message == NULL) \
		{ \
			ERROR_OCCURRED(ERROR_PACKET_HAS_NO_PAYLOAD, "Packet for " #NAME "Message has no payload.\n"); \
			return EINVAL; \
		} \
 \
		if (tosend != NULL) \
		{ \
			*message = *tosend; \
		} \
		else \
		{ \
			/* Need tosend set, so that the metrics recording works. */ \
			tosend = message; \
		} \
 \
		/* Doesn't make sense to request an ack when broadcasting. */ \
 		if (ack_request != NULL && *ack_request && target != AM_BROADCAST_ADDR) \
 		{ \
			*ack_request = call NAME##PacketAcknowledgements.requestAck(&packet) == SUCCESS; \
		} \
 \
		status = call NAME##Send.send(target, &packet, sizeof(NAME##Message)); \
		if (status == SUCCESS) \
		{ \
			SEND_LED_ON; \
			busy = TRUE; \
		} \
 \
		METRIC_BCAST(NAME, status, MSG_GET(NAME, sequence_number, tosend), call MetricHelpers.getTxPower(&packet)); \
 \
		return status; \
	} \
	else \
	{ \
		LOG_STDOUT_VERBOSE(EVENT_RADIO_BUSY, "Broadcast " #NAME " busy, not sending " #NAME " message.\n"); \
 \
		METRIC_BCAST(NAME, EBUSY, MSG_GET(NAME, sequence_number, tosend), call MetricHelpers.getTxPower(&packet)); \
 \
		return EBUSY; \
	} \
} \
inline bool send_##NAME##_message(const NAME##Message* tosend, am_addr_t target, bool* ack_request) \
{ \
	return send_##NAME##_message_ex(tosend, target, ack_request) == SUCCESS; \
}

#define SEND_MESSAGE_NO_TARGET(NAME) \
error_t send_##NAME##_message_ex(const NAME##Message* tosend) \
{ \
	if (!busy || tosend == NULL) \
	{ \
		error_t status; \
 \
		void* const void_message = call NAME##Send.getPayload(&packet, sizeof(NAME##Message)); \
		NAME##Message* const message = (NAME##Message*)void_message; \
		if (message == NULL) \
		{ \
			ERROR_OCCURRED(ERROR_PACKET_HAS_NO_PAYLOAD, "Packet for " #NAME "Message has no payload.\n"); \
			return EINVAL; \
		} \
 \
		if (tosend != NULL) \
		{ \
			*message = *tosend; \
		} \
		else \
		{ \
			/* Need tosend set, so that the metrics recording works. */ \
			tosend = message; \
		} \
 \
		status = call NAME##Send.send(&packet, sizeof(NAME##Message)); \
		if (status == SUCCESS) \
		{ \
			SEND_LED_ON; \
			busy = TRUE; \
		} \
 \
		METRIC_BCAST(NAME, status, MSG_GET(NAME, sequence_number, tosend), call MetricHelpers.getTxPower(&packet)); \
 \
		return status; \
	} \
	else \
	{ \
		LOG_STDOUT_VERBOSE(EVENT_RADIO_BUSY, "Broadcast " #NAME " busy, not sending " #NAME " message.\n"); \
 \
		METRIC_BCAST(NAME, EBUSY, MSG_GET(NAME, sequence_number, tosend), call MetricHelpers.getTxPower(&packet)); \
 \
		return EBUSY; \
	} \
} \
inline bool send_##NAME##_message(const NAME##Message* tosend) \
{ \
	return send_##NAME##_message_ex(tosend) == SUCCESS; \
}

#define SEND_DONE_NO_EXTRA_TO_SEND(NAME, CALLBACK) \
event void NAME##Send.sendDone(message_t* msg, error_t error) \
{ \
	LOG_STDOUT_VERBOSE(EVENT_SEND_DONE, #NAME " Send sendDone with status %i.\n", error); \
 \
	if (&packet == msg) \
	{ \
		SEND_LED_OFF; \
		busy = FALSE; \
	} \
 \
	(CALLBACK)(msg, error); \
}

#define SEND_DONE(NAME, CALLBACK) \
event void NAME##Send.sendDone(message_t* msg, error_t error) \
{ \
	LOG_STDOUT_VERBOSE(EVENT_SEND_DONE, #NAME " Send sendDone with status %i.\n", error); \
 \
	if (&packet == msg) \
	{ \
		if (extra_to_send > 0) \
		{ \
			if (send_##NAME##_message(NULL, call AMPacket.destination(msg))) \
			{ \
				--extra_to_send; \
			} \
			else \
			{ \
				SEND_LED_OFF; \
				busy = FALSE; \
			} \
		} \
		else \
		{ \
			SEND_LED_OFF; \
			busy = FALSE; \
		} \
	} \
 \
	(CALLBACK)(msg, error); \
}

#define SEND_DONE_NO_TARGET(NAME, CALLBACK) \
event void NAME##Send.sendDone(message_t* msg, error_t error) \
{ \
	LOG_STDOUT_VERBOSE(EVENT_SEND_DONE, #NAME " Send sendDone with status %i.\n", error); \
 \
	if (&packet == msg) \
	{ \
		SEND_LED_OFF; \
		busy = FALSE; \
	} \
 \
	(CALLBACK)(msg, error); \
}

#define RECEIVE_MESSAGE_BEGIN(NAME, KIND) \
event message_t* NAME##KIND.receive(message_t* msg, void* payload, uint8_t len) \
{ \
	const NAME##Message* const rcvd = (const NAME##Message*)payload; \
 \
	const am_addr_t source_addr = call AMPacket.source(msg); \
	const int8_t rssi = call MetricHelpers.getRssi(msg); \
	const int16_t lqi = call MetricHelpers.getLqi(msg); \
 \
 	ATTACKER_RCV(NAME, msg, source_addr, MSG_GET(NAME, source_id, rcvd), MSG_GET(NAME, sequence_number, rcvd), rssi, lqi); \
 \
	if (len != sizeof(NAME##Message)) \
	{ \
		ERROR_OCCURRED(ERROR_PACKET_HAS_INVALID_LENGTH, #KIND "ed " #NAME " of invalid length %" PRIu8 ".\n", len); \
		return msg; \
	} \
 \
	LOG_STDOUT_VERBOSE(EVENT_##KIND##_VALID_PACKET, #KIND "'ed valid " #NAME ".\n"); \
 \
	METRIC_DELIVER(NAME, source_addr, MSG_GET(NAME, source_id, rcvd), MSG_GET(NAME, sequence_number, rcvd), rssi, lqi); \
 \
	switch (call NodeType.get()) \
	{

#define RECEIVE_MESSAGE_END(NAME) \
		default: \
		{ \
			ERROR_OCCURRED(ERROR_UNKNOWN_NODE_TYPE, "Unknown node type %s. Cannot process " #NAME " message.\n", \
				call NodeType.current_to_string()); \
		} break; \
	} \
 \
	return msg; \
}

#define RECEIVE_MESSAGE_END_NO_DEFAULT(NAME) \
	} \
 \
	return msg; \
}

#define INTERCEPT_MESSAGE_BEGIN(NAME, KIND) \
event bool NAME##KIND.forward(message_t* msg, void* payload, uint8_t len) \
{ \
	NAME##Message* const rcvd = (NAME##Message*)payload; \
 \
	const am_addr_t source_addr = call AMPacket.source(msg); \
	const int8_t rssi = call MetricHelpers.getRssi(msg); \
	const int16_t lqi = call MetricHelpers.getLqi(msg); \
 \
 	ATTACKER_RCV(NAME, msg, source_addr, MSG_GET(NAME, source_id, rcvd), MSG_GET(NAME, sequence_number, rcvd), rssi, lqi); \
 \
	if (len != sizeof(NAME##Message)) \
	{ \
		ERROR_OCCURRED(ERROR_PACKET_HAS_INVALID_LENGTH, #KIND "ed " #NAME " of invalid length %" PRIu8 ".\n", len); \
		return FALSE; \
	} \
 \
	LOG_STDOUT_VERBOSE(EVENT_##KIND##_VALID_PACKET, #KIND "'ed valid " #NAME ".\n"); \
 \
	METRIC_DELIVER(NAME, source_addr, MSG_GET(NAME, source_id, rcvd), MSG_GET(NAME, sequence_number, rcvd), rssi, lqi); \
 \
	switch (call NodeType.get()) \
	{

#define INTERCEPT_MESSAGE_END(NAME) \
		default: \
		{ \
			ERROR_OCCURRED(ERROR_UNKNOWN_NODE_TYPE, "Unknown node type %s. Cannot process " #NAME " message.\n", \
				call NodeType.current_to_string()); \
		} break; \
	} \
 \
	return TRUE; \
}

#define INTERCEPT_MESSAGE_END_NO_DEFAULT(NAME) \
	} \
 \
	return TRUE; \
}


#define USE_MESSAGE_WITH_CALLBACK(NAME) \
	STATIC_ASSERT_MSG(sizeof(NAME##Message) <= TOSH_DATA_LENGTH, Need_to_increase_the_TOSH_DATA_LENGTH_for_##NAME##Message); \
	SEND_MESSAGE(NAME); \
	void send_##NAME##_done(message_t* msg, error_t error); \
	SEND_DONE(NAME, send_##NAME##_done)

#define USE_MESSAGE(NAME) \
	USE_MESSAGE_WITH_CALLBACK(NAME); \
	inline void send_##NAME##_done(message_t* msg, error_t error) {}

#define USE_MESSAGE_WITH_CALLBACK_NO_EXTRA_TO_SEND(NAME) \
	STATIC_ASSERT_MSG(sizeof(NAME##Message) <= TOSH_DATA_LENGTH, Need_to_increase_the_TOSH_DATA_LENGTH_for_##NAME##Message); \
	SEND_MESSAGE(NAME); \
	void send_##NAME##_done(message_t* msg, error_t error); \
	SEND_DONE_NO_EXTRA_TO_SEND(NAME, send_##NAME##_done)

#define USE_MESSAGE_NO_EXTRA_TO_SEND(NAME) \
	USE_MESSAGE_WITH_CALLBACK_NO_EXTRA_TO_SEND(NAME); \
	inline void send_##NAME##_done(message_t* msg, error_t error) {}

#define USE_MESSAGE_ACK_REQUEST_WITH_CALLBACK(NAME) \
	STATIC_ASSERT_MSG(sizeof(NAME##Message) <= TOSH_DATA_LENGTH, Need_to_increase_the_TOSH_DATA_LENGTH_for_##NAME##Message); \
	SEND_MESSAGE_ACK_REQUEST(NAME); \
	void send_##NAME##_done(message_t* msg, error_t error); \
	SEND_DONE_NO_EXTRA_TO_SEND(NAME, send_##NAME##_done)

#define USE_MESSAGE_ACK_REQUEST(NAME) \
	USE_MESSAGE_ACK_REQUEST_WITH_CALLBACK(NAME); \
	inline void send_##NAME##_done(message_t* msg, error_t error) {}

#define USE_MESSAGE_NO_TARGET_WITH_CALLBACK(NAME) \
	STATIC_ASSERT_MSG(sizeof(NAME##Message) <= TOSH_DATA_LENGTH, Need_to_increase_the_TOSH_DATA_LENGTH_for_##NAME##Message); \
	SEND_MESSAGE_NO_TARGET(NAME); \
	void send_##NAME##_done(message_t* msg, error_t error); \
	SEND_DONE_NO_TARGET(NAME, send_##NAME##_done)

#define USE_MESSAGE_NO_TARGET(NAME) \
	USE_MESSAGE_NO_TARGET_WITH_CALLBACK(NAME); \
	inline void send_##NAME##_done(message_t* msg, error_t error) {}


#endif // SLP_SEQUENCENUMBER_H
