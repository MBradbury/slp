#ifndef SLP_MESSAGES_EMPTYNORMALMESSAGE_H
#define SLP_MESSAGES_EMPTYNORMALMESSAGE_H

#include "SequenceNumber.h"
#include "NormalMessage.h"

typedef nx_struct EmptyNormalMessage {
    NXSequenceNumber sequence_number;
    nx_uint8_t state[sizeof(NormalMessage)];
} EmptyNormalMessage;

inline SequenceNumberWithBottom EmptyNormal_get_sequence_number(const EmptyNormalMessage* msg) { return msg->sequence_number; }
inline am_addr_t EmptyNormal_get_source_id(const EmptyNormalMessage* msg) { return AM_BROADCAST_ADDR; }

#endif // SLP_MESSAGES_EMPTYNORMALMESSAGE_H
