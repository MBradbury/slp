#ifndef SLP_MESSAGES_EMPTYNORMALMESSAGE_H
#define SLP_MESSAGES_EMPTYNORMALMESSAGE_H

//#include "SequenceNumber.h"
#include "NormalMessage.h"

typedef nx_struct EmptyNormalMessage {
    nx_uint8_t state[sizeof(NormalMessage)];
} EmptyNormalMessage;

inline SequenceNumberWithBottom EmptyNormal_get_sequence_number(const EmptyNormalMessage* msg) { return BOTTOM; }
inline int32_t EmptyNormal_get_source_id(const EmptyNormalMessage* msg) { return BOTTOM; }

#endif // SLP_MESSAGES_EMPTYNORMALMESSAGE_H
