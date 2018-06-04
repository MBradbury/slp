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

	uses interface LocalTime<TMilli>;
}
implementation
{
	void snprintf_hex_buffer(char* buf, uint8_t buf_len, const void* payload, uint8_t payload_len)
	{
		static const char* hex_str = "0123456789ABCDEF";

		const uint8_t* const payload_u8 = (const uint8_t*)payload;
		int16_t i;

		if (buf_len < payload_len * 2 + 1)
		{
			buf[0] = '\0';
			return;
		}

		if (!payload_u8)
		{
			buf[0] = '\0';
			return;
		}

		for (i = 0; i != payload_len; ++i)
		{
			buf[i * 2 + 0] = hex_str[(payload_u8[i] >> 4)       ];
			buf[i * 2 + 1] = hex_str[(payload_u8[i]     ) & 0x0F];
		}

		buf[payload_len * 2] = '\0';
	}

	command void MetricLogging.log_metric_boot()
	{
		simdbg("M-B", "booted\n");
	}

	command void MetricLogging.log_metric_receive(
		const char* message_type,
		am_addr_t proximate_source,
		am_addr_t ultimate_source,
		SequenceNumberWithBottom sequence_number,
		int16_t distance
		)
	{
		if (sequence_number <= UNKNOWN_SEQNO)
		{
			const char* sequence_number_str = sequence_number == UNKNOWN_SEQNO ? "-1" : "-2";

			simdbg("M-CR",
				MESSAGE_TYPE_SPEC "," TOS_NODE_ID_SPEC "," TOS_NODE_ID_SPEC ",%s," DISTANCE_SPEC "\n",
				MESSAGE_TYPE_CONVERTER(message_type), proximate_source, ultimate_source, sequence_number_str, distance);
		}
		else
		{
			const SequenceNumber seqno = (SequenceNumber)sequence_number;
			simdbg("M-CR",
				MESSAGE_TYPE_SPEC "," TOS_NODE_ID_SPEC "," TOS_NODE_ID_SPEC "," NXSEQUENCE_NUMBER_SPEC "," DISTANCE_SPEC "\n",
				MESSAGE_TYPE_CONVERTER(message_type), proximate_source, ultimate_source, seqno, distance);
		}
	}

	command void MetricLogging.log_metric_bcast(
		const char* message_type,
		const void* payload,
		uint8_t msg_size,
		error_t status,
		am_addr_t ultimate_source,
		SequenceNumberWithBottom sequence_number,
		uint8_t tx_power
		)
	{
		char payload_str[TOSH_DATA_LENGTH * 2 + 1];
		snprintf_hex_buffer(payload_str, ARRAY_SIZE(payload_str), payload, msg_size);

		if (sequence_number <= UNKNOWN_SEQNO)
		{
			const char* sequence_number_str = sequence_number == UNKNOWN_SEQNO ? "-1" : "-2";

			simdbg("M-CB",
				MESSAGE_TYPE_SPEC ",%" PRIu8 "," TOS_NODE_ID_SPEC ",%s,%" PRIu8 ",%s\n",
				MESSAGE_TYPE_CONVERTER(message_type), status, ultimate_source, sequence_number_str, tx_power, payload_str);
		}
		else
		{
			const SequenceNumber seqno = (SequenceNumber)sequence_number;
			simdbg("M-CB",
				MESSAGE_TYPE_SPEC ",%" PRIu8 "," TOS_NODE_ID_SPEC "," NXSEQUENCE_NUMBER_SPEC ",%" PRIu8 ",%s\n",
				MESSAGE_TYPE_CONVERTER(message_type), status, ultimate_source, seqno, tx_power, payload_str);
		}
	}

	command void MetricLogging.log_metric_deliver(
		const char* message_type,
		const message_t* msg,
		const void* payload,
		uint8_t msg_size,
		am_addr_t target,
		am_addr_t proximate_source,
		am_addr_t ultimate_source,
		SequenceNumberWithBottom sequence_number,
		int8_t rssi,
		int16_t lqi
		)
	{
		char payload_str[TOSH_DATA_LENGTH * 2 + 1];
		snprintf_hex_buffer(payload_str, ARRAY_SIZE(payload_str), payload, msg_size);

		if (sequence_number <= UNKNOWN_SEQNO)
		{
			const char* sequence_number_str = sequence_number == UNKNOWN_SEQNO ? "-1" : "-2";

			simdbg("M-CD", \
				MESSAGE_TYPE_SPEC "," TOS_NODE_ID_SPEC "," TOS_NODE_ID_SPEC "," TOS_NODE_ID_SPEC ",%s," RSSI_SPEC "," LQI_SPEC ",%s\n",
				MESSAGE_TYPE_CONVERTER(message_type), target, proximate_source, ultimate_source, sequence_number_str, rssi, lqi, payload_str);
		}
		else
		{
			const SequenceNumber seqno = (SequenceNumber)sequence_number;
			simdbg("M-CD", \
				MESSAGE_TYPE_SPEC "," TOS_NODE_ID_SPEC "," TOS_NODE_ID_SPEC "," TOS_NODE_ID_SPEC "," NXSEQUENCE_NUMBER_SPEC "," RSSI_SPEC "," LQI_SPEC ",%s\n",
				MESSAGE_TYPE_CONVERTER(message_type), target, proximate_source, ultimate_source, seqno, rssi, lqi, payload_str);
		}
	}

	command void MetricLogging.log_attacker_receive(
		const char* message_type,
		const message_t* msg,
		const void* payload,
		uint8_t msg_size,
		am_addr_t proximate_source,
		am_addr_t ultimate_source,
		SequenceNumberWithBottom sequence_number,
		int8_t rssi,
		int16_t lqi
		)
	{
		if (sequence_number <= UNKNOWN_SEQNO)
		{
			const char* sequence_number_str = sequence_number == UNKNOWN_SEQNO ? "-1" : "-2";

			simdbg("A-R",
				MESSAGE_TYPE_SPEC "," TOS_NODE_ID_SPEC "," TOS_NODE_ID_SPEC ",%s," RSSI_SPEC "," LQI_SPEC "\n",
				MESSAGE_TYPE_CONVERTER(message_type), proximate_source, ultimate_source, sequence_number_str, rssi, lqi);
		}
		else
		{
			const SequenceNumber seqno = (SequenceNumber)sequence_number;
			simdbg("A-R",
				MESSAGE_TYPE_SPEC "," TOS_NODE_ID_SPEC "," TOS_NODE_ID_SPEC "," NXSEQUENCE_NUMBER_SPEC "," RSSI_SPEC "," LQI_SPEC "\n",
				MESSAGE_TYPE_CONVERTER(message_type), proximate_source, ultimate_source, seqno, rssi, lqi);
		}
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

	command void MetricLogging.log_metric_bad_crc(
		const char* message_type,
		const void* payload,
		uint8_t msg_size,
		uint16_t rcvd_crc,
		uint16_t calc_crc
		)
	{
		char payload_str[TOSH_DATA_LENGTH * 2 + 1];
		snprintf_hex_buffer(payload_str, ARRAY_SIZE(payload_str), payload, msg_size);

		simdbgerror("stderr",
			"%" PRIu16 "," MESSAGE_TYPE_SPEC ",%04X,%04X,%s\n",
			ERROR_INVALID_CRC, MESSAGE_TYPE_CONVERTER(message_type), rcvd_crc, calc_crc, payload_str);
	}

	command void MetricLogging.log_metric_generic(
		uint16_t code,
		const char* message
		)
	{
		simdbg("M-G", "%" PRIu16 ",%s\n", code, message);
	}
}
