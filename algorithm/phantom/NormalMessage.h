#ifndef SLP_MESSAGES_NORMALMESSAGE_H
#define SLP_MESSAGES_NORMALMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct NormalMessage
{
  nx_uint64_t sequence_number;

  // The id of the node that sent this message
  nx_uint16_t source_id;

  // The number of hops that this message
  // has travelled from the source. 
  nx_uint16_t source_distance;

  nx_int16_t sink_distance_of_sender;

  nx_uint8_t further_or_closer_set;

  nx_uint32_t source_period;

} NormalMessage;

inline int64_t Normal_get_sequence_number(const NormalMessage* msg) { return msg->sequence_number; }
inline int32_t Normal_get_source_id(const NormalMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_NORMALMESSAGE_H
