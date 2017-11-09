#ifndef SLP_METRIC_LOGGING_H
#define SLP_METRIC_LOGGING_H

#include "SerialMetricLoggingTypes.h"
#include "pp.h"

#if defined(USE_SERIAL_MESSAGES) || defined(NO_SERIAL_OUTPUT)

// These are no-ops, as we cannot just put them across the line in a serial packet
#define simdbg(name, fmtstr, ...)
#define simdbg_clear(name, fmtstr, ...)
#define simdbgerror(name, fmtstr, ...)
#define simdbgerror_clear(name, fmtstr, ...)

#elif defined(TOSSIM) || defined(USE_SERIAL_PRINTF) || defined(AVRORA_OUTPUT) || defined(COOJA_OUTPUT)

#include "printf.h"

#define TOS_NODE_ID_SPEC "%" PRIu16
#define NXSEQUENCE_NUMBER_SPEC "%" PRIu32
#define SEQUENCE_NUMBER_SPEC "%" PRIi64
#define DISTANCE_SPEC "%d"
#define RSSI_SPEC "%" PRIi8
#define LQI_SPEC "%" PRIi16

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

// Any metric logging command that might want VA_ARGS can't have them
// as the nesC commands do not support them.
// To work around this we need to snprintf into a buffer before passing
// that buffer to the logging function.
#if defined(AVRORA_MAX_BUFFER_SIZE)
#define METRIC_MAX_BUFFER_SIZE AVRORA_MAX_BUFFER_SIZE
#elif defined(COOJA_MAX_BUFFER_SIZE)
#define METRIC_MAX_BUFFER_SIZE COOJA_MAX_BUFFER_SIZE
#elif defined(METRIC_MAX_BUFFER_SIZE)
// Do nothing
#else
// Default buffer size in bytes
#define METRIC_MAX_BUFFER_SIZE 128
#endif

#define METRIC_BOOT() call MetricLogging.log_metric_boot()

#define METRIC_RCV(TYPE, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER, DISTANCE) \
	call MetricLogging.log_metric_receive(#TYPE, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER, DISTANCE)

#define METRIC_BCAST(TYPE, PAYLOAD, MSG_SIZE, STATUS, ULTIMATE_SOURCE, SEQUENCE_NUMBER, TX_POWER) \
	call MetricLogging.log_metric_bcast(#TYPE, PAYLOAD, MSG_SIZE, STATUS, ULTIMATE_SOURCE, SEQUENCE_NUMBER, TX_POWER)

#define METRIC_DELIVER(TYPE, MSG, PAYLOAD, MSG_SIZE, TARGET, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER, RSSI, LQI) \
	call MetricLogging.log_metric_deliver(#TYPE, MSG, PAYLOAD, MSG_SIZE, TARGET, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER, RSSI, LQI)

#define ATTACKER_RCV(TYPE, MSG, PAYLOAD, MSG_SIZE, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER, RSSI, LQI) \
	call MetricLogging.log_attacker_receive(#TYPE, MSG, PAYLOAD, MSG_SIZE, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER, RSSI, LQI)

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

#define METRIC_RSSI(RSSI_AVERAGE, RSSI_SMALLEST, RSSI_LARGEST, RSSI_READS, CHANNEL) \
    call MetricLogging.log_metric_rssi(RSSI_AVERAGE, RSSI_SMALLEST, RSSI_LARGEST, RSSI_READS, CHANNEL)


#if defined(USE_SERIAL_MESSAGES) || defined(NO_SERIAL_OUTPUT)
#define METRIC_GENERIC(CODE, MESSAGE, ...) \
	call MetricLogging.log_metric_generic(CODE, MESSAGE)
#else
#define METRIC_GENERIC_0(CODE, MESSAGE, ...) \
	do { \
		char stdout_message[METRIC_MAX_BUFFER_SIZE]; \
		snprintf(stdout_message, ARRAY_SIZE(stdout_message), MESSAGE, ##__VA_ARGS__); \
		call MetricLogging.log_metric_generic(CODE, stdout_message); \
	} while (FALSE)

#define METRIC_GENERIC_1(CODE, MESSAGE) \
	call MetricLogging.log_metric_generic(CODE, MESSAGE)

#define METRIC_GENERIC(...) PPCAT(METRIC_GENERIC_, IS_2(NARGS(__VA_ARGS__)))(__VA_ARGS__)
#endif

// No need to format messages when using serial message as the string will not be used.
#if defined(USE_SERIAL_MESSAGES) || defined(NO_SERIAL_OUTPUT)
#define ERROR_OCCURRED(CODE, MESSAGE, ...) \
	call MetricLogging.log_error_occurred(CODE, MESSAGE)
#else
#define ERROR_OCCURRED_0(CODE, MESSAGE, ...) \
	do { \
		char error_message[METRIC_MAX_BUFFER_SIZE]; \
		snprintf(error_message, ARRAY_SIZE(error_message), MESSAGE, ##__VA_ARGS__); \
		call MetricLogging.log_error_occurred(CODE, error_message); \
	} while (FALSE)

#define ERROR_OCCURRED_1(CODE, MESSAGE) \
	call MetricLogging.log_error_occurred(CODE, MESSAGE)

#define ERROR_OCCURRED(...) PPCAT(ERROR_OCCURRED_, IS_2(NARGS(__VA_ARGS__)))(__VA_ARGS__)
#endif

// No need to format messages when using serial message as the string will not be used.
#if defined(USE_SERIAL_MESSAGES) || defined(NO_SERIAL_OUTPUT)
#define LOG_STDOUT(CODE, MESSAGE, ...) \
	call MetricLogging.log_stdout(CODE, MESSAGE)
#else
#define LOG_STDOUT_0(CODE, MESSAGE, ...) \
	do { \
		char stdout_message[METRIC_MAX_BUFFER_SIZE]; \
		snprintf(stdout_message, ARRAY_SIZE(stdout_message), MESSAGE, ##__VA_ARGS__); \
		call MetricLogging.log_stdout(CODE, stdout_message); \
	} while (FALSE)

#define LOG_STDOUT_1(CODE, MESSAGE) \
	call MetricLogging.log_stdout(CODE, MESSAGE)

#define LOG_STDOUT(...) PPCAT(LOG_STDOUT_, IS_2(NARGS(__VA_ARGS__)))(__VA_ARGS__)
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

    ERROR_RSSI_READ_FAILURE = 18,

    ERROR_BAD_HOP_DISTANCE = 19,

    ERROR_NO_MEMORY = 20,

    ERROR_INVALID_CRC = 21,

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
	EVENT_Intercept_VALID_PACKET = 2009,

	EVENT_RADIO_ENABLED = 2010,
	EVENT_RADIO_DISABLED = 2011,

	EVENT_BOOTED = 2012,

	// Only use 2xxx codes here. The reasoning for SLPErrorCodes applies.
};

#endif // SLP_METRIC_LOGGING_H
