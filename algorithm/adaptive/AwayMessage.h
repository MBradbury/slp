#ifndef SLP_MESSAGES_AWAYMESSAGE_H
#define SLP_MESSAGES_AWAYMESSAGE_H

#include "SequenceNumber.h"
#include "HopDistance.h"

typedef nx_struct AwayMessage {
  NXSequenceNumber sequence_number;

  nx_am_addr_t source_id;

  // The sink and sink-source distances must be known
  // by the time an away or choose message is sent.
  // Although not necessarily the correct distance,
  // as the known distance may be higher.
  nx_hop_distance_t sink_distance;

  nx_hop_distance_t max_hop;

  nx_uint8_t algorithm;

} AwayMessage;

inline SequenceNumberWithBottom Away_get_sequence_number(const AwayMessage* msg) { return msg->sequence_number; }
inline am_addr_t Away_get_source_id(const AwayMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_AWAYMESSAGE_H
