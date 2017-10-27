#ifndef SLP_MESSAGES_FAKEMESSAGE_H
#define SLP_MESSAGES_FAKEMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct FakeMessage {
  NXSequenceNumber sequence_number;
  
  nx_am_addr_t source_id;

  nx_uint16_t source_distance;

} FakeMessage;

inline SequenceNumberWithBottom Fake_get_sequence_number(const FakeMessage* msg) { return msg->sequence_number; }
inline am_addr_t Fake_get_source_id(const FakeMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_FAKEMESSAGE_H
