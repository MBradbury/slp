#ifndef SLP_MESSAGES_MOVEMESSAGE_H
#define SLP_MESSAGES_MOVEMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct MoveMessage {
  nx_uint64_t sequence_number;

#if 0
  // The id of the node that sent this message
  nx_am_addr_t source_id;

  nx_uint16_t source_distance;
  nx_uint16_t sink_distance;
  nx_uint16_t sink_source_distance;

  nx_uint16_t max_hop;

  nx_uint8_t from_pfs;
#endif

} MoveMessage;

#endif // SLP_MESSAGES_MOVEMESSAGE_H
