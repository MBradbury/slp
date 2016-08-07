#ifndef SLP_METRIC_LOGGING_H
#define SLP_METRIC_LOGGING_H

#if defined(USE_SERIAL_MESSAGES)

#elif defined(TOSSIM) || defined(USE_SERIAL_PRINTF)

#define MSG_TYPE_SPEC "%s"
#define TOS_NODE_ID_SPEC "%u"

// Time is a uint32_t when deploying on real hardware is it comes from LocalTime.
// In a simulator time is sim_time_t which is a long long int.
#ifdef USE_SERIAL_PRINTF
#	define SIM_TIME_SPEC "%" PRIu32
#else
// For some reason PRIi64 doesn't reliably work, so use the manual lli
//#	define SIM_TIME_SPEC "%" PRIi64
#	define SIM_TIME_SPEC "%lli"
#endif

#define PROXIMATE_SOURCE_SPEC TOS_NODE_ID_SPEC
#define ULTIMATE_SOURCE_SPEC "%d"
#define ULTIMATE_SOURCE_POSS_BOTTOM_SPEC "%" PRIi32
#define NXSEQUENCE_NUMBER_SPEC "%" PRIu32
#define SEQUENCE_NUMBER_SPEC "%" PRIi64
#define DISTANCE_SPEC "%d"

// The SEQUENCE_NUMBER parameter will typically be of type NXSequenceNumber or have the value BOTTOM,
// this is why it needs to be cast to an int64_t first.
#define METRIC_RCV(TYPE, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER, DISTANCE) \
	simdbg("M-C", \
		"RCV:" MSG_TYPE_SPEC "," \
		PROXIMATE_SOURCE_SPEC "," ULTIMATE_SOURCE_SPEC "," SEQUENCE_NUMBER_SPEC "," DISTANCE_SPEC "\n", \
		#TYPE, \
		PROXIMATE_SOURCE, ULTIMATE_SOURCE, (int64_t)SEQUENCE_NUMBER, DISTANCE)

#define METRIC_BCAST(TYPE, STATUS, SEQUENCE_NUMBER) \
	simdbg("M-C", \
		"BCAST:" MSG_TYPE_SPEC ",%u," SEQUENCE_NUMBER_SPEC "\n", \
		#TYPE, \
		STATUS, (int64_t)SEQUENCE_NUMBER)

#define METRIC_DELIVER(TYPE, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER) \
	simdbg("M-C", \
		"DELIV:" MSG_TYPE_SPEC "," \
		PROXIMATE_SOURCE_SPEC "," ULTIMATE_SOURCE_POSS_BOTTOM_SPEC "," SEQUENCE_NUMBER_SPEC "\n", \
		#TYPE, \
		PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER)

#define ATTACKER_RCV(NAME, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER) \
	simdbg("A-R", \
		"%s," PROXIMATE_SOURCE_SPEC "," ULTIMATE_SOURCE_POSS_BOTTOM_SPEC "," SEQUENCE_NUMBER_SPEC "\n", \
		NAME, PROXIMATE_SOURCE, ULTIMATE_SOURCE, SEQUENCE_NUMBER)

#define METRIC_SOURCE_CHANGE(TYPE) \
	simdbg("M-SC", TYPE "\n")

#else
#	error "Unknown configuration"
#endif

#endif // SLP_METRIC_LOGGING_H
