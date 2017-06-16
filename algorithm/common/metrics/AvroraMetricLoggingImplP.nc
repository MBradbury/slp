#include "MetricLogging.h"

#ifndef CYCLEACCURATE_AVRORA
#	error "Must only be used by Avrora"
#endif

// Note that GCC doesn't support a 64 bit print specifier for the AVR libc.
// So we need to specially handle those values.

#if 0
#	define MESSAGE_TYPE_SPEC "%" PRIu8
#	define MESSAGE_TYPE_CONVERTER(message_type) call MessageType.from_string(message_type)
#else
#	define MESSAGE_TYPE_SPEC "%s"
#	define MESSAGE_TYPE_CONVERTER(message_type) message_type
#endif

module AvroraMetricLoggingImplP
{
	provides interface MetricLogging;

	uses interface MessageType;

	uses interface LocalTime<TMilli>;

	uses interface AvroraPrintf;
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
		if (sequence_number == BOTTOM)
		{
			simdbg("M-CR",
				MESSAGE_TYPE_SPEC, "," PROXIMATE_SOURCE_SPEC "," ULTIMATE_SOURCE_SPEC ",-1," DISTANCE_SPEC "\n",
				MESSAGE_TYPE_CONVERTER(message_type), proximate_source, ultimate_source, distance);
		}
		else
		{
			const SequenceNumber seqno = (SequenceNumber)sequence_number;
			simdbg("M-CR",
				MESSAGE_TYPE_SPEC, "," PROXIMATE_SOURCE_SPEC "," ULTIMATE_SOURCE_SPEC "," NXSEQUENCE_NUMBER_SPEC "," DISTANCE_SPEC "\n",
				MESSAGE_TYPE_CONVERTER(message_type), proximate_source, ultimate_source, seqno, distance);
		}
	}

	command void MetricLogging.log_metric_bcast(
		const char* message_type,
		error_t status,
		SequenceNumberWithBottom sequence_number
		)
	{
		if (sequence_number == BOTTOM)
		{
			simdbg("M-CB",
				MESSAGE_TYPE_SPEC, ",%" PRIu8 ",-1\n",
				MESSAGE_TYPE_CONVERTER(message_type), status);
		}
		else
		{
			const SequenceNumber seqno = (SequenceNumber)sequence_number;
			simdbg("M-CB",
				MESSAGE_TYPE_SPEC ",%" PRIu8 "," NXSEQUENCE_NUMBER_SPEC "\n",
				MESSAGE_TYPE_CONVERTER(message_type), status, seqno);
		}
	}

	command void MetricLogging.log_metric_deliver(
		const char* message_type,
		am_addr_t proximate_source,
		int32_t ultimate_source_poss_bottom,
		SequenceNumberWithBottom sequence_number
		)
	{
		if (sequence_number == BOTTOM)
		{
			simdbg("M-CD", \
				MESSAGE_TYPE_SPEC, "," PROXIMATE_SOURCE_SPEC "," ULTIMATE_SOURCE_POSS_BOTTOM_SPEC ",-1\n",
				MESSAGE_TYPE_CONVERTER(message_type), proximate_source, ultimate_source_poss_bottom);
		}
		else
		{
			const SequenceNumber seqno = (SequenceNumber)sequence_number;
			simdbg("M-CD", \
				MESSAGE_TYPE_SPEC, "," PROXIMATE_SOURCE_SPEC "," ULTIMATE_SOURCE_POSS_BOTTOM_SPEC "," NXSEQUENCE_NUMBER_SPEC "\n",
				MESSAGE_TYPE_CONVERTER(message_type), proximate_source, ultimate_source_poss_bottom, seqno);
		}

		
	}

	command void MetricLogging.log_attacker_receive(
		const char* message_type,
		const message_t* msg,
		am_addr_t proximate_source,
		int32_t ultimate_source_poss_bottom,
		SequenceNumberWithBottom sequence_number
		)
	{
		if (sequence_number == BOTTOM)
		{
			simdbg("A-R",
				MESSAGE_TYPE_SPEC, "," PROXIMATE_SOURCE_SPEC "," ULTIMATE_SOURCE_POSS_BOTTOM_SPEC ",-1\n",
				MESSAGE_TYPE_CONVERTER(message_type), proximate_source, ultimate_source_poss_bottom);
		}
		else
		{
			const SequenceNumber seqno = (SequenceNumber)sequence_number;
			simdbg("A-R",
				MESSAGE_TYPE_SPEC, "," PROXIMATE_SOURCE_SPEC "," ULTIMATE_SOURCE_POSS_BOTTOM_SPEC "," NXSEQUENCE_NUMBER_SPEC "\n",
				MESSAGE_TYPE_CONVERTER(message_type), proximate_source, ultimate_source_poss_bottom, seqno);
		}
	}

	command void MetricLogging.log_metric_node_change(
		uint8_t old_type,
		const char* old_type_str,
		uint8_t new_type,
		const char* new_type_str
		)
	{
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
		simdbg("stdout", "%s", message);
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
	}
}
