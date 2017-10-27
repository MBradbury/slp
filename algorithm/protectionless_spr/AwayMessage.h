#ifndef SLP_MESSAGES_AWAYMESSAGE_H
#define SLP_MESSAGES_AWAYMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct AwayMessage {
  NXSequenceNumber sequence_number;

  // The number of hops that this message
  // has travelled from the source. 
  nx_uint16_t source_distance;

  // The id of the node that sent this message
  nx_am_addr_t source_id;

} AwayMessage;

inline SequenceNumberWithBottom Away_get_sequence_number(const AwayMessage* msg) { return msg->sequence_number; }
inline am_addr_t Away_get_source_id(const AwayMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_AWAYMESSAGE_H
