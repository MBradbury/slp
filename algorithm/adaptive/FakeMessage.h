#ifndef SLP_MESSAGES_FAKEMESSAGE_H
#define SLP_MESSAGES_FAKEMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct FakeMessage {
  nx_uint64_t sequence_number;

  // The id of the node that sent this message
  nx_uint16_t source_id;

  nx_uint16_t source_distance;
  nx_uint16_t sink_distance;
  nx_uint16_t sink_source_distance;

  nx_uint8_t from_pfs;

  nx_uint16_t max_hop;

} FakeMessage;

#endif // SLP_MESSAGES_FAKEMESSAGE_H
