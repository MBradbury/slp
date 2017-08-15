#include "MetricLogging.h"

// By converting message type from a string to an int
// we should reduce the number of characters that need to be
// printed over the serial interface.
// This should increase the reliability of the output, at a cost
// of some CPU usage to convert from a string to an int.
#ifdef USE_SERIAL_PRINTF
#	define MESSAGE_TYPE_SPEC "%" PRIu8
#	define MESSAGE_TYPE_CONVERTER(message_type) call MessageType.from_string(message_type)
#else
#	define MESSAGE_TYPE_SPEC "%s"
#	define MESSAGE_TYPE_CONVERTER(message_type) message_type
#endif

module PrintfMetricLoggingImplP
{
	provides interface MetricLogging;

	uses interface MessageType;

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
		simdbg("M-CR",
			MESSAGE_TYPE_SPEC "," PROXIMATE_SOURCE_SPEC "," ULTIMATE_SOURCE_SPEC "," SEQUENCE_NUMBER_SPEC "," DISTANCE_SPEC "\n",
			MESSAGE_TYPE_CONVERTER(message_type), proximate_source, ultimate_source, sequence_number, distance);
	}

	command void MetricLogging.log_metric_bcast(
		const char* message_type,
		error_t status,
		SequenceNumberWithBottom sequence_number,
		uint8_t tx_power
		)
	{
		simdbg("M-CB",
			MESSAGE_TYPE_SPEC ",%" PRIu8 "," SEQUENCE_NUMBER_SPEC ",%" PRIu8 "\n",
			MESSAGE_TYPE_CONVERTER(message_type), status, sequence_number, tx_power);
	}

	command void MetricLogging.log_metric_deliver(
		const char* message_type,
		am_addr_t proximate_source,
		int32_t ultimate_source_poss_bottom,
		SequenceNumberWithBottom sequence_number,
		int8_t rssi,
		int16_t lqi
		)
	{
		simdbg("M-CD", \
			MESSAGE_TYPE_SPEC "," PROXIMATE_SOURCE_SPEC "," ULTIMATE_SOURCE_POSS_BOTTOM_SPEC "," SEQUENCE_NUMBER_SPEC "," RSSI_SPEC "," LQI_SPEC "\n",
			MESSAGE_TYPE_CONVERTER(message_type), proximate_source, ultimate_source_poss_bottom, sequence_number, rssi, lqi);
	}

	command void MetricLogging.log_attacker_receive(
		const char* message_type,
		const message_t* msg,
		am_addr_t proximate_source,
		int32_t ultimate_source_poss_bottom,
		SequenceNumberWithBottom sequence_number,
		int8_t rssi,
		int16_t lqi
		)
	{
		simdbg("A-R",
			MESSAGE_TYPE_SPEC "," PROXIMATE_SOURCE_SPEC "," ULTIMATE_SOURCE_POSS_BOTTOM_SPEC "," SEQUENCE_NUMBER_SPEC "," RSSI_SPEC "," LQI_SPEC "\n",
			MESSAGE_TYPE_CONVERTER(message_type), proximate_source, ultimate_source_poss_bottom, sequence_number, rssi, lqi);
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
		simdbg("M-NTA", "%" PRIu8 ",%s\n", node_type_id, node_type_name);
	}

	command void MetricLogging.log_metric_message_type_add(
		uint8_t message_type_id,
		const char* message_type_name
		)
	{
		simdbg("M-MTA", "%" PRIu8 ",%s\n", message_type_id, message_type_name);
	}

    command void MetricLogging.log_metric_fault_point_type_add(
            uint8_t fault_point_id,
            const char* fault_point_name
            )
    {
        simdbg("M-FPA", "%" PRIu8 ",%s\n", fault_point_id, fault_point_name);
    }

    command void MetricLogging.log_metric_fault_point(
            uint8_t fault_point_id
            )
    {
        simdbg("M-FP", "%" PRIu8 "\n", fault_point_id);
    }

	command void MetricLogging.log_error_occurred(
		uint16_t code,
		const char* message
		)
	{
		// No newline here, message needs to provide it!
		simdbgerror("stderr", "%" PRIu16 ",%s", code, message);
	}

	command void MetricLogging.log_stdout(
		uint16_t code,
		const char* message
		)
	{
		// No newline here, message needs to provide it!
		simdbg("stdout", "%" PRIu16 ",%s", code, message);
	}

	//##########SLP TDMA DAS##########
	command void MetricLogging.log_metric_node_slot_change(
		uint16_t old_slot,
		uint16_t new_slot
		)
	{
		simdbg("M-NSC", "%" PRIu16 ",%" PRIu16 "\n", old_slot, new_slot);
	}

    command void MetricLogging.log_metric_start_period()
    {
        simdbg("M-SP", "\n");
    }

	//##########Tree based routing##########
	command void MetricLogging.log_metric_parent_change(
		am_addr_t old_parent,
		am_addr_t new_parent
		)
	{
		simdbg("M-PC", TOS_NODE_ID_SPEC "," TOS_NODE_ID_SPEC "\n", old_parent, new_parent);

		simdbg("G-A", "arrow,-," TOS_NODE_ID_SPEC "," TOS_NODE_ID_SPEC ",(0,0,0)\n", TOS_NODE_ID, old_parent);
		simdbg("G-A", "arrow,+," TOS_NODE_ID_SPEC "," TOS_NODE_ID_SPEC ",(0,0,0)\n", TOS_NODE_ID, new_parent);
	}

	command void MetricLogging.log_metric_rssi(
		uint16_t average,
		uint16_t smallest,
		uint16_t largest,
		uint16_t reads,
		uint8_t channel
		)
	{
		simdbg("M-RSSI",
				"%" PRIu16 ",%" PRIu16 ",%" PRIu16 ",%" PRIu16 ",%" PRIu8 "\n",
				average, smallest, largest, reads, channel);
	}
}
