#ifndef SLP_MESSAGES_AWAYMESSAGE_H
#define SLP_MESSAGES_AWAYMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct AwayMessage
{
  NXSequenceNumber sequence_number;

  nx_am_addr_t source_id;

  nx_uint16_t landmark_distance;

} AwayMessage;

inline SequenceNumberWithBottom Away_get_sequence_number(const AwayMessage* msg) { return msg->sequence_number; }
inline am_addr_t Away_get_source_id(const AwayMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_AWAYMESSAGE_H
