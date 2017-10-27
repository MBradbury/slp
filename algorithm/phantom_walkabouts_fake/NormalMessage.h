#ifndef SLP_MESSAGES_NORMALMESSAGE_H
#define SLP_MESSAGES_NORMALMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct NormalMessage
{
  NXSequenceNumber sequence_number;

  // The id of the node that sent this message
  nx_int16_t source_id;

  // The number of hops that this message
  // has travelled from the source. 
  nx_int16_t source_distance;

  nx_int16_t bottom_left_distance;

  nx_int16_t bottom_right_distance;

  nx_int16_t sink_distance;

  nx_int8_t further_or_closer_set;

  nx_int8_t broadcast;

  nx_int16_t random_walk_hops;

  nx_int16_t neighbour_size;

  nx_int16_t node_id;

  nx_int16_t sink_source_distance;

  nx_int16_t source_message_send_no;


} NormalMessage;

inline SequenceNumberWithBottom Normal_get_sequence_number(const NormalMessage* msg) { return msg->sequence_number; }
inline am_addr_t Normal_get_source_id(const NormalMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_NORMALMESSAGE_H
