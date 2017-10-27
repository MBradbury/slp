#ifndef SLP_MESSAGES_AWAYMESSAGE_H
#define SLP_MESSAGES_AWAYMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct AwayMessage
{
  NXSequenceNumber sequence_number;

  nx_am_addr_t source_id;

  // The number of hops that this message
  // has travelled from the landmark node. 
  nx_int16_t landmark_distance;

  nx_int16_t sink_bl_dist;

  nx_int16_t sink_br_dist;

  nx_int16_t landmark_location;

  nx_int16_t node_id;

  nx_int16_t neighbour_size;

} AwayMessage;

inline SequenceNumberWithBottom Away_get_sequence_number(const AwayMessage* msg) { return msg->sequence_number; }

inline am_addr_t Away_get_source_id(const AwayMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_AWAYMESSAGE_H
