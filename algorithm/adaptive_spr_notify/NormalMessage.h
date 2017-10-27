#ifndef SLP_MESSAGES_NORMALMESSAGE_H
#define SLP_MESSAGES_NORMALMESSAGE_H

#include "SequenceNumber.h"
#include "HopDistance.h"

typedef nx_struct NormalMessage {
  NXSequenceNumber sequence_number;

  NXSequenceNumber fake_sequence_number;
  nx_uint32_t fake_sequence_increments;

  // The number of hops that this message
  // has travelled from the source. 
  nx_hop_distance_t source_distance;

  // The id of the node that sent this message
  nx_am_addr_t source_id;

  //nx_int16_t sink_source_distance;

} NormalMessage;

inline SequenceNumberWithBottom Normal_get_sequence_number(const NormalMessage* msg) { return msg->sequence_number; }
inline am_addr_t Normal_get_source_id(const NormalMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_NORMALMESSAGE_H
