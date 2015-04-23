#ifndef SLP_MESSAGES_AWAYMESSAGE_H
#define SLP_MESSAGES_AWAYMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct AwayMessage
{
  nx_uint64_t sequence_number;

  nx_am_addr_t source_id;

  // The number of hops that this message
  // has travelled from the sink. 
  nx_uint16_t sink_distance;

} AwayMessage;

#endif // SLP_MESSAGES_AWAYMESSAGE_H
