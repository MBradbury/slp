#ifndef SLP_MESSAGES_AWAYCHOOSEMESSAGE_H
#define SLP_MESSAGES_AWAYCHOOSEMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct AwayChooseMessage {
  nx_uint32_t sequence_number;

  // The id of the node that sent this message
  nx_uint16_t source_id;

  nx_int16_t sink_source_distance;

  // The number of hops that this message
  // has travelled from the source. 
  nx_uint16_t sink_distance;

  nx_uint16_t max_hop;

  

} AwayChooseMessage;

typedef AwayChooseMessage AwayMessage;
typedef AwayChooseMessage ChooseMessage;

#endif // SLP_MESSAGES_AWAYCHOOSEMESSAGE_H
