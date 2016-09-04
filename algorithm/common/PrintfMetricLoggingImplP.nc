#include "MetricLogging.h"

module PrintfMetricLoggingImplP
{
	provides interface MetricLogging;

#ifdef USE_SERIAL_PRINTF
	uses interface LocalTime<TMilli>;
#endif
}
implementation
{
	command void MetricLogging.log_metric_receive(
		const char* message_type,
		am_addr_t proximate_source,
		am_addr_t ultimate_source,
		SequenceNumberWithBottom sequence_number,
		int16_t distance
		)
	{
		simdbg("M-C",
			"RCV:%s," PROXIMATE_SOURCE_SPEC "," ULTIMATE_SOURCE_SPEC "," SEQUENCE_NUMBER_SPEC "," DISTANCE_SPEC "\n",
			message_type, proximate_source, ultimate_source, sequence_number, distance);
	}

	command void MetricLogging.log_metric_bcast(
		const char* message_type,
		error_t status,
		SequenceNumberWithBottom sequence_number
		)
	{
		simdbg("M-C",
			"BCAST:%s,%u," SEQUENCE_NUMBER_SPEC "\n",
			message_type, status, sequence_number);
	}

	command void MetricLogging.log_metric_deliver(
		const char* message_type,
		am_addr_t proximate_source,
		int32_t ultimate_source_poss_bottom,
		SequenceNumberWithBottom sequence_number
		)
	{
		simdbg("M-C", \
			"DELIV:%s," PROXIMATE_SOURCE_SPEC "," ULTIMATE_SOURCE_POSS_BOTTOM_SPEC "," SEQUENCE_NUMBER_SPEC "\n",
			message_type, proximate_source, ultimate_source_poss_bottom, sequence_number);
	}

	command void MetricLogging.log_attacker_receive(
		const char* message_type,
		am_addr_t proximate_source,
		int32_t ultimate_source_poss_bottom,
		SequenceNumberWithBottom sequence_number
		)
	{
		simdbg("A-R",
			"%s," PROXIMATE_SOURCE_SPEC "," ULTIMATE_SOURCE_POSS_BOTTOM_SPEC "," SEQUENCE_NUMBER_SPEC "\n",
			message_type, proximate_source, ultimate_source_poss_bottom, sequence_number);
	}

	command void MetricLogging.log_metric_node_change(
		uint8_t old_type,
		const char* old_type_str,
		uint8_t new_type,
		const char* new_type_str
		)
	{
		// One event to handle metrics and other for the GUI
		simdbg("M-NC", "%s,%s\n", old_type_str, new_type_str);
		simdbg("G-NC", "%s,%s\n", old_type_str, new_type_str);
	}

	command void MetricLogging.log_metric_node_type_add(
		uint8_t node_type_id,
		const char* node_type_name
		)
	{
		simdbg("M-NTA", "%u,%s\n", node_type_id, node_type_name);
	}

	command void MetricLogging.log_metric_message_type_add(
		uint8_t message_type_id,
		const char* message_type_name
		)
	{
		simdbg("M-MTA", "%u,%s\n", message_type_id, message_type_name);
	}

	command void MetricLogging.log_error_occurred(
		uint16_t code,
		const char* message
		)
	{
		// No newline here, message needs to provide it!
		simdbgerror("stderr", "%s", message);
	}

	//##########SLP TDMA DAS##########
	command void MetricLogging.log_metric_node_slot_change(
		uint16_t old_slot,
		uint16_t new_slot
		)
	{
		simdbg("M-NSC", "%u,%u\n", old_slot, new_slot);
	}
}
