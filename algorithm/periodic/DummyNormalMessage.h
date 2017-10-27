#ifndef SLP_MESSAGES_DUMMYNORMALMESSAGE_H
#define SLP_MESSAGES_DUMMYNORMALMESSAGE_H

#include "NormalMessage.h"

typedef nx_struct DummyNormalMessage {
	nx_uint8_t state[sizeof(NormalMessage)];

} DummyNormalMessage;

inline SequenceNumberWithBottom DummyNormal_get_sequence_number(const DummyNormalMessage* msg) { return BOTTOM; }
inline am_addr_t DummyNormal_get_source_id(const DummyNormalMessage* msg) { return AM_BROADCAST_ADDR; }

#endif // SLP_MESSAGES_DUMMYNORMALMESSAGE_H
