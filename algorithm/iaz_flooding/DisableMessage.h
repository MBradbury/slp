#ifndef SLP_MESSAGES_DISABLEMESSAGE_H
#define SLP_MESSAGES_DISABLEMESSAGE_H

#include "Common.h"

typedef nx_struct DisableMessage {
  nx_am_addr_t source_id;

  nx_uint16_t hop_limit;

} DisableMessage;

inline SequenceNumberWithBottom Disable_get_sequence_number(const DisableMessage* msg) { return UNKNOWN_SEQNO; }
inline int32_t Disable_get_source_id(const DisableMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_DISABLEMESSAGE_H
