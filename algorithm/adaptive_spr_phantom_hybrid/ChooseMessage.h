#ifndef SLP_MESSAGES_CHOOSEMESSAGE_H
#define SLP_MESSAGES_CHOOSEMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct ChooseMessage {
  NXSequenceNumber sequence_number;

  nx_am_addr_t source_id;

  nx_uint16_t sender_distance;
  
  nx_uint8_t algorithm;

} ChooseMessage;

inline SequenceNumberWithBottom Choose_get_sequence_number(const ChooseMessage* msg) { return msg->sequence_number; }
inline am_addr_t Choose_get_source_id(const ChooseMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_AWAYCHOOSEMESSAGE_H
