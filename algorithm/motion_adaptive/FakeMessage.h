#ifndef SLP_MESSAGES_FAKEMESSAGE_H
#define SLP_MESSAGES_FAKEMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct FakeMessage {
  nx_uint32_t sequence_number;

  // The id of the node that sent this message
  nx_am_addr_t source_id;

  // Distances of the first sender
  nx_uint16_t source_distance;
  nx_uint16_t sink_distance;

  // The current ssd
  nx_uint16_t sink_source_distance;

  nx_uint16_t max_hop;

  nx_uint8_t from_pfs;

  // Distances of 1-hop sender
  nx_int16_t source_distance_of_sender;
  nx_int16_t sink_distance_of_sender;

} FakeMessage;

#endif // SLP_MESSAGES_FAKEMESSAGE_H
