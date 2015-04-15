#ifndef SLP_MESSAGES_NORMALMESSAGE_H
#define SLP_MESSAGES_NORMALMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct NormalMessage {
  nx_uint64_t sequence_number;

  // The number of hops that this message
  // has travelled from the source. 
  nx_uint16_t source_distance;

  // The id of the node that sent this message
  nx_am_addr_t source_id;

  nx_uint16_t max_hop;

  nx_int16_t sink_source_distance;

  nx_uint64_t fake_sequence_number;
  nx_uint32_t fake_sequence_increments;

  nx_uint32_t source_period;

  nx_int16_t source_distance_of_sender;
  nx_int16_t sink_distance_of_sender;
  
} NormalMessage;

#endif // SLP_MESSAGES_NORMALMESSAGE_H
