#ifndef SLP_MESSAGES_AWAYMESSAGE_H
#define SLP_MESSAGES_AWAYMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct AwayMessage {
  NXSequenceNumber sequence_number;

  nx_am_addr_t source_id;

  // The sink and sink-source distances must be known
  // by the time an away or choose message is sent.
  // Although not necessarily the correct distance,
  // as the known distance may be higher.
  nx_uint16_t sink_distance;
  //nx_uint16_t sink_source_distance;

} AwayMessage;

inline SequenceNumberWithBottom Away_get_sequence_number(const AwayMessage* msg) { return msg->sequence_number; }
inline int32_t Away_get_source_id(const AwayMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_AWAYMESSAGE_H
