#include "SequenceNumber.h"

interface MetricLogging
{
	command void log_metric_receive(
		const char* message_type,
		am_addr_t proximate_source,
		am_addr_t ultimate_source,
		SequenceNumberWithBottom sequence_number,
		int16_t distance
		);

	command void log_metric_bcast(
		const char* message_type,
		error_t status,
		SequenceNumberWithBottom sequence_number
		);

	command void log_metric_deliver(
		const char* message_type,
		am_addr_t proximate_source,
		int32_t ultimate_source_poss_bottom,
		SequenceNumberWithBottom sequence_number
		);

	command void log_attacker_receive(
		const char* message_type,
		am_addr_t proximate_source,
		int32_t ultimate_source_poss_bottom,
		SequenceNumberWithBottom sequence_number
		);

	command void log_metric_node_change(
		uint8_t old_type,
		const char* old_type_str,
		uint8_t new_type,
		const char* new_type_str
		);

	command void log_error_occurred(
		uint16_t code,
		const char* message
		);
}
