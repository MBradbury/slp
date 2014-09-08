#ifndef SLP_MESSAGES_NORMALMESSAGE_H
#define SLP_MESSAGES_NORMALMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct NormalMessage {
  nx_uint32_t sequence_number;

  nx_int16_t sink_source_distance;

  // The number of hops that this message
  // has travelled from the source. 
  nx_uint16_t hop;

  nx_uint16_t max_hop;

  // The id of the node that sent this message
  nx_uint16_t source_id;

} NormalMessage;

#endif // SLP_MESSAGES_NORMALMESSAGE_H
