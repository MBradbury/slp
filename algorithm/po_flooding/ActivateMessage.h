#ifndef SLP_MESSAGES_ACTIVATEMESSAGE_H
#define SLP_MESSAGES_ACTIVATEMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct ActivateMessage {
  NXSequenceNumber sequence_number;

  nx_am_addr_t source_id;

  nx_uint16_t sink_distance;

  nx_uint8_t previous_normal_forward_enabled;

} ActivateMessage;

inline SequenceNumberWithBottom Activate_get_sequence_number(const ActivateMessage* msg) { return msg->sequence_number; }
inline am_addr_t Activate_get_source_id(const ActivateMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_ACTIVATEMESSAGE_H
