#ifndef SLP_MESSAGES_NOTIFYMESSAGE_H
#define SLP_MESSAGES_NOTIFYMESSAGE_H

#include "SequenceNumber.h"
#include "HopDistance.h"

typedef nx_struct NotifyMessage {
  NXSequenceNumber sequence_number;

  // The id of the node that sent this message
  nx_am_addr_t source_id;

  nx_hop_distance_t source_distance;

} NotifyMessage;

inline SequenceNumberWithBottom Notify_get_sequence_number(const NotifyMessage* msg) { return msg->sequence_number; }
inline am_addr_t Notify_get_source_id(const NotifyMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_NOTIFYMESSAGE_H
