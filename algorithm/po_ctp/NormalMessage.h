#ifndef SLP_MESSAGES_NORMALMESSAGE_H
#define SLP_MESSAGES_NORMALMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct NormalMessage {
  NXSequenceNumber sequence_number;

  // The id of the node that sent this message
  nx_am_addr_t source_id;

  nx_uint16_t source_distance;

} NormalMessage;

inline SequenceNumberWithBottom Normal_get_sequence_number(const NormalMessage* msg) { return msg->sequence_number; }
inline am_addr_t Normal_get_source_id(const NormalMessage* msg) { return msg->source_id; }

typedef NormalMessage NormalFloodMessage;

#define NormalFlood_get_sequence_number Normal_get_sequence_number
#define NormalFlood_get_source_id Normal_get_source_id

#endif // SLP_MESSAGES_NORMALMESSAGE_H
