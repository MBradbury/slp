#ifndef SLP_MESSAGES_AWAYMESSAGE_H
#define SLP_MESSAGES_AWAYMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct AwayMessage
{
  NXSequenceNumber sequence_number;

  nx_am_addr_t source_id;

  // The number of hops that this message
  // has travelled from the landmark node. 
  nx_uint16_t landmark_distance;

  nx_uint16_t sink_bl_dist;

  nx_uint16_t sink_br_dist;

  nx_uint16_t sink_tr_dist;

  nx_uint8_t bottom_left_or_right;

} AwayMessage;

inline SequenceNumberWithBottom Away_get_sequence_number(const AwayMessage* msg) { return msg->sequence_number; }

inline int32_t Away_get_source_id(const AwayMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_AWAYMESSAGE_H
