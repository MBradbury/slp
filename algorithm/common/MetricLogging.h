#ifndef SLP_METRIC_LOGGING_H
#define SLP_METRIC_LOGGING_H

#if defined(USE_SERIAL_MESSAGES)

// The common start that all messages should have is:
// nx_uint8_t type; // This is the type of debug/metric message
// nx_am_addr_t node_id;
// nx_uint32_t local_time;

// These constants are used to set the message type
#define UNKNOWN_TYPE 0

#define METRIC_RCV_TYPE 1
#define METRIC_BCAST_TYPE 2
#define METRIC_DELIVER_TYPE 3
#define ATTACKER_RCV_TYPE 4
#define METRIC_SOURCE_CHANGE_TYPE 5

nx_struct metric_rcv_msg {
	nx_uint8_t type;
	nx_am_addr_t node_id;
	nx_uint32_t local_time;

	nx_uint8_t message_type;

	nx_am_addr_t proximate_source;
	nx_int16_t ultimate_source;

	nx_int64_t sequence_number;

	nx_int16_t distance;
};

#define METRIC_RCV(TYPE, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER, DISTANCE) \
	do { \
		metric_rcv_msg message; \
		message.type = METRIC_RCV_TYPE; \
		message.node_id = TOS_NODE_ID; \
		message.local_time = call LocalTime.get(); \
		message.message_type = TYPE; \
		message.proximate_source = PROXIMATE_SOURCE; \
		message.ultimate_source = ULTIMATE_SOURCE; \
		message.sequence_number = SEQUENCE_NUMBER; \
		message.distance = DISTANCE; 
 \
		/* TODO: Send message*/ \
 \
	} while (FALSE)

nx_struct metric_bcast_msg {
	nx_uint8_t type;
	nx_am_addr_t node_id;
	nx_uint32_t local_time;

	nx_uint8_t message_type;

	nx_int16_t status;

	nx_int64_t sequence_number;
};

nx_struct metric_deliver_msg {
	nx_uint8_t type;
	nx_am_addr_t node_id;
	nx_uint32_t local_time;

	nx_uint8_t message_type;

	nx_am_addr_t proximate_source;
	nx_int32_t ultimate_source_poss_bottom;
	nx_int64_t sequence_number;
};

nx_struct attacker_rcv_msg {
	nx_uint8_t type;
	nx_am_addr_t node_id;
	nx_uint32_t local_time;

	nx_uint8_t message_type;

	nx_am_addr_t proximate_source;
	nx_int32_t ultimate_source_poss_bottom;
	nx_int64_t sequence_number;
};

nx_struct metric_source_change_msg {
	nx_uint8_t type;
	nx_am_addr_t node_id;
	nx_uint32_t local_time;

	nx_uint8_t change_kind; // 0 if set, 1 if unset
};

#elif defined(TOSSIM) || defined(USE_SERIAL_PRINTF)

#define TOS_NODE_ID_SPEC "%u"

#define PROXIMATE_SOURCE_SPEC TOS_NODE_ID_SPEC
#define ULTIMATE_SOURCE_SPEC TOS_NODE_ID_SPEC
#define ULTIMATE_SOURCE_POSS_BOTTOM_SPEC "%" PRIi32
#define NXSEQUENCE_NUMBER_SPEC "%" PRIu32
#define SEQUENCE_NUMBER_SPEC "%" PRIi64
#define DISTANCE_SPEC "%d"

// The SEQUENCE_NUMBER parameter will typically be of type NXSequenceNumber or have the value BOTTOM,
// this is why it needs to be cast to an int64_t first.
#define METRIC_RCV(TYPE, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER, DISTANCE) \
	simdbg("M-C", \
		"RCV:" #TYPE "," \
		PROXIMATE_SOURCE_SPEC "," ULTIMATE_SOURCE_SPEC "," SEQUENCE_NUMBER_SPEC "," DISTANCE_SPEC "\n", \
		PROXIMATE_SOURCE, ULTIMATE_SOURCE, (int64_t)SEQUENCE_NUMBER, DISTANCE)

#define METRIC_BCAST(TYPE, STATUS, SEQUENCE_NUMBER) \
	simdbg("M-C", \
		"BCAST:" #TYPE ",%u," SEQUENCE_NUMBER_SPEC "\n", \
		STATUS, (int64_t)SEQUENCE_NUMBER)

#define METRIC_DELIVER(TYPE, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER) \
	simdbg("M-C", \
		"DELIV:" #TYPE "," \
		PROXIMATE_SOURCE_SPEC "," ULTIMATE_SOURCE_POSS_BOTTOM_SPEC "," SEQUENCE_NUMBER_SPEC "\n", \
		PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER)

#define ATTACKER_RCV(TYPE, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER) \
	simdbg("A-R", \
		#TYPE "," \
		PROXIMATE_SOURCE_SPEC "," ULTIMATE_SOURCE_POSS_BOTTOM_SPEC "," SEQUENCE_NUMBER_SPEC "\n", \
		PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER)

#define METRIC_SOURCE_CHANGE(TYPE) \
	simdbg("M-SC", TYPE "\n")

#else
#	error "Unknown configuration"
#endif

#endif // SLP_METRIC_LOGGING_H
