#ifndef SLP_MESSAGES_LOOPMESSAGE_H
#define SLP_MESSAGES_LOOPMESSAGE_H

#include "utils.h"

typedef nx_struct LoopMessage {
  nx_am_addr_t source_id;
  IDList loop;
  nx_int32_t dist;
} LoopMessage;

inline int64_t Loop_get_sequence_number(const LoopMessage* msg) { return BOTTOM; }
inline int32_t Loop_get_source_id(const LoopMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_LOOPMESSAGE_H
