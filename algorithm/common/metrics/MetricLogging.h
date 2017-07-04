#ifndef SLP_METRIC_LOGGING_H
#define SLP_METRIC_LOGGING_H

#include "SerialMetricLoggingTypes.h"

#if defined(USE_SERIAL_MESSAGES) || defined(NO_SERIAL_OUTPUT)

// These are no-ops, as we cannot just put them across the line in a serial packet
#define simdbg(name, fmtstr, ...)
#define simdbg_clear(name, fmtstr, ...)
#define simdbgerror(name, fmtstr, ...)
#define simdbgerror_clear(name, fmtstr, ...)

#elif defined(TOSSIM) || defined(USE_SERIAL_PRINTF) || defined(AVRORA_OUTPUT)

#include "printf.h"

#define TOS_NODE_ID_SPEC "%" PRIu16

#define PROXIMATE_SOURCE_SPEC TOS_NODE_ID_SPEC
#define ULTIMATE_SOURCE_SPEC TOS_NODE_ID_SPEC
#define ULTIMATE_SOURCE_POSS_BOTTOM_SPEC "%" PRIi32
#define NXSEQUENCE_NUMBER_SPEC "%" PRIu32
#define SEQUENCE_NUMBER_SPEC "%" PRIi64
#define DISTANCE_SPEC "%d"

// avr-libc doesn't support 64 bit format specifier
// See: http://www.nongnu.org/avr-libc/user-manual/group__avr__stdio.html#gaa3b98c0d17b35642c0f3e4649092b9f1
#ifdef __AVR_LIBC_VERSION__
#undef PRIi64
#undef PRIu64
#undef SEQUENCE_NUMBER_SPEC
#endif

#else
#	error "Unknown configuration"
#endif

#if defined(USE_SERIAL_PRINTF) || (defined(CYCLEACCURATE_AVRORA) && defined(AVRORA_OUTPUT))
#	define METRIC_LOGGING_NEEDS_LOCALTIME
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

#define METRIC_FAULT_POINT_TYPE_ADD(FAULT_POINT_ID, FAULT_POINT_NAME) \
    call MetricLogging.log_metric_fault_point_type_add(FAULT_POINT_ID, FAULT_POINT_NAME)

#define METRIC_FAULT_POINT(FAULT_POINT_ID) \
    call MetricLogging.log_metric_fault_point(FAULT_POINT_ID)

#define METRIC_START_PERIOD() \
    call MetricLogging.log_metric_start_period()

// No need to format messages when using serial message as the string will not be used.
#if defined(USE_SERIAL_MESSAGES) || defined(NO_SERIAL_OUTPUT)
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

// No need to format messages when using serial message as the string will not be used.
#if defined(USE_SERIAL_MESSAGES) || defined(NO_SERIAL_OUTPUT)
#define LOG_STDOUT(CODE, MESSAGE, ...) \
	call MetricLogging.log_stdout(CODE, MESSAGE)
#else
#define LOG_STDOUT(CODE, MESSAGE, ...) \
	do { \
		char stdout_message[256]; \
		snprintf(stdout_message, ARRAY_SIZE(stdout_message), MESSAGE, ##__VA_ARGS__); \
		call MetricLogging.log_stdout(CODE, stdout_message); \
	} while (FALSE)
#endif

#ifdef SLP_VERBOSE_DEBUG
#	define LOG_STDOUT_VERBOSE LOG_STDOUT
#else
#	define LOG_STDOUT_VERBOSE(CODE, MESSAGE, ...)
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

	ERROR_NODE_NAME_TOO_LONG = 10,
	ERROR_MESSAGE_NAME_TOO_LONG = 11,

	ERROR_REACHED_UNREACHABLE = 12,
	ERROR_ASSERT = 13,

	ERROR_POOL_EMPTY = 14,
	ERROR_QUEUE_EMPTY = 15,

    ERROR_TOO_MANY_FAULT_POINT_TYPES = 16,
    ERROR_FAULT_POINT_NAME_TOO_LONG = 17,

	// Fake message based algorithm error codes
	ERROR_CALLED_FMG_CALC_PERIOD_ON_NON_FAKE_NODE = 101,
	ERROR_SEND_FAKE_PERIOD_ZERO = 102,

	// Do not use error codes 1xxx as they are reserved for application
	// specific errors.

	// Do not use event codes 2xxx as they are reserved for general events.

	// Do not use event codes 3xxx as they are reserved for application
	// specific events.
};

enum SLPEventCodes {
	EVENT_OBJECT_DETECTED = 2001,
	EVENT_OBJECT_STOP_DETECTED = 2002,

	EVENT_RADIO_BUSY = 2003,
	EVENT_SEND_DONE = 2004,

	EVENT_RADIO_ON = 2005,
	EVENT_RADIO_OFF = 2006,

	// Yes the capitalisation is odd, but it needs to be this way
	EVENT_Receive_VALID_PACKET = 2007,
	EVENT_Snoop_VALID_PACKET = 2008,

	// Only use 2xxx codes here. The reasoning for SLPErrorCodes applies.
};

#endif // SLP_METRIC_LOGGING_H
