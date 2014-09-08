#ifndef SLP_MESSAGES_FAKEMESSAGE_H
#define SLP_MESSAGES_FAKEMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct FakeMessage {
  nx_uint32_t sequence_number;

  nx_int16_t sink_source_distance;

  nx_uint16_t source_distance;

  nx_uint16_t max_hop;

  // The number of hops that this message is allowed to travel
  nx_uint16_t travel_dist;

  nx_uint16_t from_sink_distance;

  nx_uint8_t from_permanent_fs;

  nx_uint16_t source_id;

} FakeMessage;

#endif // SLP_MESSAGES_FAKEMESSAGE_H
