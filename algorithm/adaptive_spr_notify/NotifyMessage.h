#ifndef SLP_MESSAGES_NOTIFYMESSAGE_H
#define SLP_MESSAGES_NOTIFYMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct NotifyMessage {
  // The id of the node that sent this message
  nx_am_addr_t source_id;

} NotifyMessage;

inline SequenceNumberWithBottom Notify_get_sequence_number(const NotifyMessage* msg) { return SEQNO_UNKNOWN; }
inline int32_t Notify_get_source_id(const NotifyMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_NOTIFYMESSAGE_H
