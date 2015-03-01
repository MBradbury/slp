#ifndef SLP_MESSAGES_DUMMYNORMALMESSAGE_H
#define SLP_MESSAGES_DUMMYNORMALMESSAGE_H

#include "SequenceNumber.h"
#include "NormalMessage.h"

typedef nx_struct DummyNormalMessage {
	nx_uint64_t sequence_number;
	nx_uint8_t state[sizeof(NormalMessage) - sizeof(nx_uint64_t)];

} DummyNormalMessage;

#endif // SLP_MESSAGES_DUMMYNORMALMESSAGE_H
