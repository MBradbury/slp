#ifndef SLP_MESSAGES_AWAYCHOOSEMESSAGE_H
#define SLP_MESSAGES_AWAYCHOOSEMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct AwayChooseMessage {
  nx_uint32_t sequence_number;
  

  // The sink and sink-source distances must be known
  // by the time an away or choose message is sent.
  // Although not necessarily the correct distance,
  // as the known distance may be higher.
  nx_uint16_t sink_distance;
  nx_uint16_t sink_source_distance;

  nx_uint16_t max_hop;

  nx_am_addr_t source_id;

  nx_uint8_t algorithm;

  nx_uint32_t source_period;

  // Distances of 1-hop sender
  nx_int16_t source_distance_of_sender;
  nx_int16_t sink_distance_of_sender;

} AwayChooseMessage;

typedef AwayChooseMessage AwayMessage;
typedef AwayChooseMessage ChooseMessage;

#endif // SLP_MESSAGES_AWAYCHOOSEMESSAGE_H
