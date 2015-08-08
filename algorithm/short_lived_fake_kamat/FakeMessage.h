#ifndef SLP_MESSAGES_FAKEMESSAGE_H
#define SLP_MESSAGES_FAKEMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct FakeMessage {
  nx_uint64_t sequence_number;

  // The id of the node that sent this message
  nx_am_addr_t source_id;

} FakeMessage;

inline int64_t Fake_get_sequence_number(const FakeMessage* msg) { return msg->sequence_number; }
inline int32_t Fake_get_source_id(const FakeMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_FAKEMESSAGE_H
