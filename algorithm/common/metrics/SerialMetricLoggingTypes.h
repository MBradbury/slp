#ifndef SLP_SERIAL_METRIC_LOGGING_H
#define SLP_SERIAL_METRIC_LOGGING_H

#include "AM.h"

// These constants are used to set the message channel and type
// The format of the name is required by the mig tool.
// Please update simulator/OfflineLogConverter.py when you change
// any of these values.
enum {
	AM_EVENT_OCCURRED_MSG = 48,
	AM_ERROR_OCCURRED_MSG = 49,
	AM_METRIC_RECEIVE_MSG = 50,
	AM_METRIC_BCAST_MSG = 51,
	AM_METRIC_DELIVER_MSG = 52,
	AM_ATTACKER_RECEIVE_MSG = 53,
	AM_METRIC_NODE_CHANGE_MSG = 54,
	AM_METRIC_NODE_TYPE_ADD_MSG = 55,
	AM_METRIC_MESSAGE_TYPE_ADD_MSG = 56,
	// SLP TDMA DAS
	AM_METRIC_NODE_SLOT_CHANGE_MSG = 57,
	// Tree based routing
	AM_METRIC_PARENT_CHANGE_MSG = 58,
    //SLP TDMA DAS
    AM_METRIC_START_PERIOD_MSG = 59,

    AM_METRIC_FAULT_POINT_TYPE_ADD_MSG = 60,
    AM_METRIC_FAULT_POINT_MSG = 61,

    AM_METRIC_RSSI_MSG = 62,
};

#define MAXIMUM_NODE_TYPE_NAME_LENGTH 20
#define MAXIMUM_MESSAGE_TYPE_NAME_LENGTH 20
#define MAXIMUM_FAULT_POINT_TYPE_NAME_LENGTH 20

#define METRIC_LOGGING_HEADER \
	nx_am_id_t type; /* This is the type of debug/metric message*/ \
	nx_am_addr_t node_id; \
	nx_uint32_t local_time;

typedef nx_struct metric_receive_msg {
	METRIC_LOGGING_HEADER

	nx_uint8_t message_type;

	nx_am_addr_t proximate_source;
	nx_int16_t ultimate_source;

	nx_int64_t sequence_number;

	nx_int16_t distance;
} metric_receive_msg_t;

typedef nx_struct metric_bcast_msg {
	METRIC_LOGGING_HEADER

	nx_uint8_t message_type;

	nx_uint8_t status; // nx type for error_t

	nx_int64_t sequence_number;
} metric_bcast_msg_t;

typedef nx_struct metric_deliver_msg {
	METRIC_LOGGING_HEADER

	nx_uint8_t message_type;

	nx_am_addr_t proximate_source;
	nx_int32_t ultimate_source_poss_bottom;
	nx_int64_t sequence_number;
	nx_int8_t rssi;
} metric_deliver_msg_t;

typedef nx_struct attacker_receive_msg {
	METRIC_LOGGING_HEADER
	nx_uint8_t message_type;

	nx_am_addr_t proximate_source;
	nx_int32_t ultimate_source_poss_bottom;
	nx_int64_t sequence_number;
	nx_int8_t rssi;
} attacker_receive_msg_t;

typedef nx_struct metric_node_change_msg {
	METRIC_LOGGING_HEADER

	nx_uint8_t old_node_type;
	nx_uint8_t new_node_type;
} metric_node_change_msg_t;

typedef nx_struct metric_node_type_add_msg {
	METRIC_LOGGING_HEADER

	nx_uint8_t node_type_id;
	nx_uint8_t node_type_name[MAXIMUM_NODE_TYPE_NAME_LENGTH];

} metric_node_type_add_msg_t;

typedef nx_struct metric_message_type_add_msg {
	METRIC_LOGGING_HEADER

	nx_uint8_t message_type_id;
	nx_uint8_t message_type_name[MAXIMUM_MESSAGE_TYPE_NAME_LENGTH];

} metric_message_type_add_msg_t;

typedef nx_struct metric_fault_point_type_add_msg {
    METRIC_LOGGING_HEADER

    nx_uint8_t fault_point_id;
    nx_uint8_t fault_point_name[MAXIMUM_FAULT_POINT_TYPE_NAME_LENGTH];

} metric_fault_point_type_add_msg_t;

typedef nx_struct metric_fault_point_msg {
    METRIC_LOGGING_HEADER

    nx_uint8_t fault_point_id;
} metric_fault_point_msg_t;

typedef nx_struct error_occurred_msg {
	METRIC_LOGGING_HEADER

	nx_uint16_t error_code;
} error_occurred_msg_t;

typedef nx_struct event_occurred_msg {
	METRIC_LOGGING_HEADER

	nx_uint16_t event_code;
} event_occurred_msg_t;

//##########SLP TDMA DAS##########
typedef nx_struct metric_node_slot_change_msg {
	METRIC_LOGGING_HEADER

	nx_uint16_t old_slot;
	nx_uint16_t new_slot;
} metric_node_slot_change_msg_t;

typedef nx_struct metric_start_period_msg {
    METRIC_LOGGING_HEADER

} metric_start_period_msg_t;

//##########Tree based routing##########
typedef nx_struct metric_parent_change_msg {
	METRIC_LOGGING_HEADER

	nx_am_addr_t old_parent;
	nx_am_addr_t new_parent;
} metric_parent_change_msg_t;

typedef nx_struct metric_rssi_msg {
	METRIC_LOGGING_HEADER

	nx_uint16_t average;
	nx_uint16_t smallest;
	nx_uint16_t largest;
	nx_uint16_t reads;
	nx_uint8_t channel;

} metric_rssi_msg_t;

#endif // SLP_SERIAL_METRIC_LOGGING_H
