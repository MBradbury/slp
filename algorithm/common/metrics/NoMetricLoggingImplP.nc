#include "MetricLogging.h"

module NoMetricLoggingImplP
{
	provides interface MetricLogging;

	uses interface MessageType;
}
implementation
{
	command void MetricLogging.log_metric_boot()
	{

	}

	command void MetricLogging.log_metric_receive(
		const char* message_type,
		am_addr_t proximate_source,
		am_addr_t ultimate_source,
		SequenceNumberWithBottom sequence_number,
		int16_t distance
		)
	{
	}

	command void MetricLogging.log_metric_bcast(
		const char* message_type,
		error_t status,
		SequenceNumberWithBottom sequence_number,
		uint8_t tx_power
		)
	{
	}

	command void MetricLogging.log_metric_deliver(
		const char* message_type,
		am_addr_t target,
		am_addr_t proximate_source,
		int32_t ultimate_source_poss_bottom,
		SequenceNumberWithBottom sequence_number,
		int8_t rssi,
		int16_t lqi
		)
	{
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
	}

	command void MetricLogging.log_metric_node_change(
		uint8_t old_type,
		const char* old_type_str,
		uint8_t new_type,
		const char* new_type_str
		)
	{
	}

	command void MetricLogging.log_metric_node_type_add(
		uint8_t node_type_id,
		const char* node_type_name
		)
	{
	}

	command void MetricLogging.log_metric_message_type_add(
		uint8_t message_type_id,
		const char* message_type_name
		)
	{
	}

    command void MetricLogging.log_metric_fault_point_type_add(
            uint8_t fault_point_id,
            const char* fault_point_name
            )
    {
    }

    command void MetricLogging.log_metric_fault_point(
            uint8_t fault_point_id
            )
    {
    }

	command void MetricLogging.log_error_occurred(
		uint16_t code,
		const char* message
		)
	{
	}

	command void MetricLogging.log_stdout(
		uint16_t code,
		const char* message
		)
	{
	}

	//##########SLP TDMA DAS##########
	command void MetricLogging.log_metric_node_slot_change(
		uint16_t old_slot,
		uint16_t new_slot
		)
	{
	}

    command void MetricLogging.log_metric_start_period()
    {
    }

	//##########Tree based routing##########
	command void MetricLogging.log_metric_parent_change(
		am_addr_t old_parent,
		am_addr_t new_parent
		)
	{
	}

	command void MetricLogging.log_metric_rssi(
		uint16_t average,
		uint16_t smallest,
		uint16_t largest,
		uint16_t reads,
		uint8_t channel
		)
	{
	}
}
