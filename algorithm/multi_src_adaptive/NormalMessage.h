#ifndef SLP_MESSAGES_NORMALMESSAGE_H
#define SLP_MESSAGES_NORMALMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct NormalMessage {
  nx_uint64_t sequence_number;

  // The number of hops that this message
  // has travelled from the source. 
  nx_uint16_t source_distance;

  nx_uint16_t average_1hop_source_distance;

  // The id of the node that sent this message
  nx_am_addr_t source_id;

  nx_int16_t sink_source_distance;

  nx_uint64_t fake_sequence_number;
  nx_uint32_t fake_sequence_increments;

} NormalMessage;

#endif // SLP_MESSAGES_NORMALMESSAGE_H
