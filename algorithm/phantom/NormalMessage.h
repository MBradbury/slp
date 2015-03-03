#ifndef SLP_MESSAGES_NORMALMESSAGE_H
#define SLP_MESSAGES_NORMALMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct NormalMessage
{
  nx_uint64_t sequence_number;

  // The id of the node that sent this message
  nx_uint16_t source_id;
  
  // the remain hops of the node
  //nx_uint16_t source_hop;

  // The number of hops that this message
  // has travelled from the source. 
  nx_uint16_t source_distance;

  //nx_uint16_t source_des;

  nx_int16_t sink_distance;

  nx_uint8_t further_or_closer_set;

} NormalMessage;

#endif // SLP_MESSAGES_NORMALMESSAGE_H
