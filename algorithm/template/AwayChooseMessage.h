#ifndef SLP_MESSAGES_AWAYCHOOSEMESSAGE_H
#define SLP_MESSAGES_AWAYCHOOSEMESSAGE_H

#include "SequenceNumber.h"
#include "HopDistance.h"

typedef nx_struct AwayChooseMessage {
  NXSequenceNumber sequence_number;

  // The sink and sink-source distances must be known
  // by the time an away or choose message is sent.
  // Although not necessarily the correct distance,
  // as the known distance may be higher.
  nx_hop_distance_t sink_distance;
  nx_hop_distance_t sink_source_distance;

  nx_hop_distance_t max_hop;

  nx_uint8_t algorithm;

} AwayChooseMessage;

typedef AwayChooseMessage AwayMessage;
typedef AwayChooseMessage ChooseMessage;

inline SequenceNumberWithBottom AwayChoose_get_sequence_number(const AwayChooseMessage* msg) { return msg->sequence_number; }
inline am_addr_t AwayChoose_get_source_id(const AwayChooseMessage* msg) { return AM_BROADCAST_ADDR; }

#define Away_get_sequence_number AwayChoose_get_sequence_number
#define Away_get_source_id AwayChoose_get_source_id

#define Choose_get_sequence_number AwayChoose_get_sequence_number
#define Choose_get_source_id AwayChoose_get_source_id

#endif // SLP_MESSAGES_AWAYCHOOSEMESSAGE_H
