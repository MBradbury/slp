#ifndef SLP_MESSAGES_FAKEMESSAGE_H
#define SLP_MESSAGES_FAKEMESSAGE_H

#include "SequenceNumber.h"
#include "HopDistance.h"

typedef nx_struct FakeMessage {
  NXSequenceNumber sequence_number;

  // The id of the node that sent this message
  nx_am_addr_t source_id;

  nx_hop_distance_t sender_source_distance;
  nx_hop_distance_t sink_distance;
  nx_hop_distance_t sink_source_distance;

  nx_hop_distance_t max_hop;

  nx_uint8_t from_pfs;

} FakeMessage;

inline SequenceNumberWithBottom Fake_get_sequence_number(const FakeMessage* msg) { return msg->sequence_number; }
inline am_addr_t Fake_get_source_id(const FakeMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_FAKEMESSAGE_H
