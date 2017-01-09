#ifndef SLP_METRIC_LOGGING_H
#define SLP_METRIC_LOGGING_H

#if defined(USE_SERIAL_MESSAGES)

#include "SerialMetricLoggingTypes.h"

// These are no-ops, as we cannot just put them across the line in a serial packet
#define simdbg(name, fmtstr, ...)
#define simdbg_clear(name, fmtstr, ...)
#define simdbgerror(name, fmtstr, ...)
#define simdbgerror_clear(name, fmtstr, ...)

#elif defined(TOSSIM) || defined(USE_SERIAL_PRINTF)

#define TOS_NODE_ID_SPEC "%u"

#define PROXIMATE_SOURCE_SPEC TOS_NODE_ID_SPEC
#define ULTIMATE_SOURCE_SPEC TOS_NODE_ID_SPEC
#define ULTIMATE_SOURCE_POSS_BOTTOM_SPEC "%" PRIi32
#define NXSEQUENCE_NUMBER_SPEC "%" PRIu32
#define SEQUENCE_NUMBER_SPEC "%" PRIi64
#define DISTANCE_SPEC "%d"

#else
#	error "Unknown configuration"
#endif

#define METRIC_RCV(TYPE, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER, DISTANCE) \
	call MetricLogging.log_metric_receive(#TYPE, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER, DISTANCE)

#define METRIC_BCAST(TYPE, STATUS, SEQUENCE_NUMBER) \
	call MetricLogging.log_metric_bcast(#TYPE, STATUS, SEQUENCE_NUMBER)

#define METRIC_DELIVER(TYPE, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER) \
	call MetricLogging.log_metric_deliver(#TYPE, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER)

#define ATTACKER_RCV(TYPE, MSG, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER) \
	call MetricLogging.log_attacker_receive(#TYPE, MSG, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER)

#define METRIC_NODE_CHANGE(OLD_TYPE, OLD_TYPE_STR, NEW_TYPE, NEW_TYPE_STR) \
	call MetricLogging.log_metric_node_change(OLD_TYPE, OLD_TYPE_STR, NEW_TYPE, NEW_TYPE_STR)

#define METRIC_NODE_TYPE_ADD(NODE_TYPE_ID, NODE_TYPE_NAME) \
	call MetricLogging.log_metric_node_type_add(NODE_TYPE_ID, NODE_TYPE_NAME)

#define METRIC_MESSAGE_TYPE_ADD(MESSAGE_TYPE_ID, MESSAGE_TYPE_NAME) \
	call MetricLogging.log_metric_message_type_add(MESSAGE_TYPE_ID, MESSAGE_TYPE_NAME)

// No need to format messages when using serial message as the string will not be used.
#ifdef USE_SERIAL_MESSAGES
#define ERROR_OCCURRED(CODE, MESSAGE, ...) \
	call MetricLogging.log_error_occurred(CODE, MESSAGE)
#else
#define ERROR_OCCURRED(CODE, MESSAGE, ...) \
	do { \
		char error_message[256]; \
		snprintf(error_message, ARRAY_SIZE(error_message), MESSAGE, ##__VA_ARGS__); \
		call MetricLogging.log_error_occurred(CODE, error_message); \
	} while (FALSE)
#endif

// Error codes for events that need to be passed on over a serial connection
enum SLPErrorCodes {
	ERROR_UNKNOWN = 0,

	// General error codes
	ERROR_RADIO_CONTROL_START_FAIL = 1,
	ERROR_PACKET_HAS_NO_PAYLOAD = 2,
	ERROR_UNKNOWN_NODE_TYPE = 3,
	ERROR_PACKET_HAS_INVALID_LENGTH = 4,
	ERROR_POOL_FULL = 5,
	ERROR_TOO_MANY_NODE_TYPES = 6,
	ERROR_TOO_MANY_MESSAGE_TYPES = 7,
	ERROR_QUEUE_FULL = 8,
	ERROR_DICTIONARY_KEY_NOT_FOUND = 9,

	// Fake message based algorithm error codes
	ERROR_CALLED_FMG_CALC_PERIOD_ON_NON_FAKE_NODE = 101,
	ERROR_SEND_FAKE_PERIOD_ZERO = 102,
};

#endif // SLP_METRIC_LOGGING_H
