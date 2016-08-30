#ifndef SLP_MESSAGES_EMPTYNORMALMESSAGE_H
#define SLP_MESSAGES_EMPTYNORMALMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct EmptyNormalMessage {
  NXSequenceNumber sequence_number;

  // The id of the node that sent this message
  nx_am_addr_t source_id;

} EmptyNormalMessage;

inline SequenceNumberWithBottom EmptyNormal_get_sequence_number(const EmptyNormalMessage* msg) { return msg->sequence_number; }
inline int32_t EmptyNormal_get_source_id(const EmptyNormalMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_EMPTYNORMALMESSAGE_H
