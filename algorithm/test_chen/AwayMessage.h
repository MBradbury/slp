#ifndef SLP_MESSAGES_AWAYMESSAGE_H
#define SLP_MESSAGES_AWAYMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct AwayMessage
{
  NXSequenceNumber bottom_left_sequence_number;
  NXSequenceNumber bottom_right_sequence_number;

  nx_am_addr_t source_id;

  // The number of hops that this message
  // has travelled from the landmark node. 
  nx_uint16_t landmark_bottom_left_distance;

  nx_uint16_t landmark_bottom_right_distance;

  nx_uint8_t bottom_left_or_right;

} AwayMessage;

inline SequenceNumberWithBottom Away_get_bottom_left_sequence_number(const AwayMessage* msg) { return msg->bottom_left_sequence_number; }
inline SequenceNumberWithBottom Away_get_bottom_right_sequence_number(const AwayMessage* msg) { return msg->bottom_right_sequence_number; }

inline int32_t Away_get_source_id(const AwayMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_AWAYMESSAGE_H
