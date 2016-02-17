#ifndef SLP_SENDRECEIVEFUNCTIONS_H
#define SLP_SENDRECEIVEFUNCTIONS_H

#include "pp.h"

#define MSG_TYPE_SPEC "%s"
#define SIM_TIME_SPEC "%" PRIu64
#define TOS_NODE_ID_SPEC "%u"

#define PROXIMATE_SOURCE_SPEC "%u"
#define ULTIMATE_SOURCE_SPEC "%d"
#define SEQUENCE_NUMBER_SPEC "%" PRIi64
#define DISTANCE_SPEC "%d"

#define METRIC_RCV(TYPE, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER, DISTANCE) \
	dbg_clear("Metric-COMMUNICATE", \
		"RCV:" MSG_TYPE_SPEC "," SIM_TIME_SPEC "," TOS_NODE_ID_SPEC "," \
		PROXIMATE_SOURCE_SPEC "," ULTIMATE_SOURCE_SPEC "," SEQUENCE_NUMBER_SPEC "," DISTANCE_SPEC "\n", \
		#TYPE, sim_time(), TOS_NODE_ID, \
		PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER, DISTANCE)

#define METRIC_BCAST(TYPE, STATUS, SEQUENCE_NUMBER) \
	dbg_clear("Metric-COMMUNICATE", \
		"BCAST:" MSG_TYPE_SPEC "," SIM_TIME_SPEC "," TOS_NODE_ID_SPEC ",%s," SEQUENCE_NUMBER_SPEC "\n", \
		#TYPE, sim_time(), TOS_NODE_ID, \
		STATUS, SEQUENCE_NUMBER)

#define METRIC_DELIVER(TYPE, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER) \
	dbg_clear("Metric-COMMUNICATE", \
		"DELIVER:" MSG_TYPE_SPEC "," SIM_TIME_SPEC "," TOS_NODE_ID_SPEC "," PROXIMATE_SOURCE_SPEC "," ULTIMATE_SOURCE_SPEC "," SEQUENCE_NUMBER_SPEC "\n", \
		#TYPE, sim_time(), TOS_NODE_ID, \
		PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER)

#define MSG_GET_NAME(TYPE, NAME) PPCAT(PPCAT(TYPE, _get_), NAME)
#define MSG_GET(TYPE, NAME, MSG) MSG_GET_NAME(TYPE, NAME)(MSG)

#define SEND_MESSAGE(NAME) \
error_t send_##NAME##_message_ex(const NAME##Message* tosend, am_addr_t target) \
{ \
	if (!busy || tosend == NULL) \
	{ \
		error_t status; \
 \
		void* const void_message = call Packet.getPayload(&packet, sizeof(NAME##Message)); \
		NAME##Message* const message = (NAME##Message*)void_message; \
		if (sizeof(NAME##Message) > TOSH_DATA_LENGTH) \
		{ \
			dbgerror("stdout", "%s: Packet payload for " #NAME "Message is too large %u > %u.\n", \
				sim_time_string(), sizeof(NAME##Message), TOSH_DATA_LENGTH); \
			return ESIZE; \
		} \
		if (message == NULL) \
		{ \
			dbgerror("stdout", "%s: Packet for " #NAME "Message has no payload.\n", sim_time_string()); \
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
			call Leds.led0On(); \
			busy = TRUE; \
 \
			METRIC_BCAST(NAME, "success", MSG_GET(NAME, sequence_number, tosend)); \
		} \
		else \
		{ \
			METRIC_BCAST(NAME, "failed", MSG_GET(NAME, sequence_number, tosend)); \
		} \
		return status; \
	} \
	else \
	{ \
		dbgverbose("stdout", "%s: Broadcast" #NAME "Timer busy, not sending " #NAME " message.\n", sim_time_string()); \
 \
		METRIC_BCAST(NAME, "busy", MSG_GET(NAME, sequence_number, tosend)); \
 \
		return EBUSY; \
	} \
} \
inline bool send_##NAME##_message(const NAME##Message* tosend, am_addr_t target) \
{ \
	return send_##NAME##_message_ex(tosend, target) == SUCCESS; \
}


#define SEND_DONE(NAME, CALLBACK) \
event void NAME##Send.sendDone(message_t* msg, error_t error) \
{ \
	dbgverbose("stdout", "%s: " #NAME "Send sendDone with status %i.\n", \
		sim_time_string(), error); \
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
				call Leds.led0Off(); \
				busy = FALSE; \
			} \
		} \
		else \
		{ \
			call Leds.led0Off(); \
			busy = FALSE; \
		} \
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
 \
	dbg_clear("Attacker-RCV", SIM_TIME_SPEC ",%s," TOS_NODE_ID_SPEC "," PROXIMATE_SOURCE_SPEC "," ULTIMATE_SOURCE_SPEC "," SEQUENCE_NUMBER_SPEC "\n", \
		sim_time(), #NAME, TOS_NODE_ID, source_addr, MSG_GET(NAME, source_id, rcvd), MSG_GET(NAME, sequence_number, rcvd)); \
 \
	if (len != sizeof(NAME##Message)) \
	{ \
		dbgerror("SourceBroadcasterC", "%s: " #KIND "ed " #NAME " of invalid length %hhu.\n", sim_time_string(), len); \
		return msg; \
	} \
 \
	dbgverbose("SourceBroadcasterC", "%s: " #KIND "ed valid " #NAME ".\n", sim_time_string()); \
 \
	METRIC_DELIVER(NAME, source_addr, MSG_GET(NAME, source_id, rcvd), MSG_GET(NAME, sequence_number, rcvd)); \
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

#define USE_MESSAGE(NAME) \
	SEND_MESSAGE(NAME); \
	inline void send_##NAME##_done(message_t* msg, error_t error); \
	SEND_DONE(NAME, send_##NAME##_done); \
	inline void send_##NAME##_done(message_t* msg, error_t error) {}

#define USE_MESSAGE_WITH_CALLBACK(NAME) \
	SEND_MESSAGE(NAME); \
	void send_##NAME##_done(message_t* msg, error_t error); \
	SEND_DONE(NAME, send_##NAME##_done)

#endif // SLP_SEQUENCENUMBER_H
