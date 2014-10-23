#ifndef SLP_MESSAGES_NORMALMESSAGE_H
#define SLP_MESSAGES_NORMALMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct NormalMessage {
  nx_uint64_t sequence_number;

  // The number of hops that this message
  // has travelled from the source. 
  nx_uint16_t source_distance;

  // The id of the node that sent this message
  nx_uint16_t source_id;

  nx_uint16_t max_hop;

  nx_int16_t sink_source_distance;

} NormalMessage;

#endif // SLP_MESSAGES_NORMALMESSAGE_H
