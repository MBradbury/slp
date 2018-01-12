#ifndef SLP_MESSAGES_CHOOSEMESSAGE_H
#define SLP_MESSAGES_CHOOSEMESSAGE_H

#include "SequenceNumber.h"
#include "HopDistance.h"

typedef nx_struct ChooseMessage {
  NXSequenceNumber sequence_number;

  nx_am_addr_t source_id;

  // The sink and sink-source distances must be known
  // by the time an away or choose message is sent.
  // Although not necessarily the correct distance,
  // as the known distance may be higher.
  nx_hop_distance_t sink_distance;

  nx_uint8_t algorithm;

  nx_uint8_t any_further; // Does the sender believe there to be any nodes further from the source?

  nx_uint8_t source_node_type;
  nx_hop_distance_t ultimate_sender_first_source_distance;

} ChooseMessage;

inline SequenceNumberWithBottom Choose_get_sequence_number(const ChooseMessage* msg) { return msg->sequence_number; }
inline am_addr_t Choose_get_source_id(const ChooseMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_CHOOSEMESSAGE_H
