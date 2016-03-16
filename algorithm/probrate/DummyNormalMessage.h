#ifndef SLP_MESSAGES_DUMMYNORMALMESSAGE_H
#define SLP_MESSAGES_DUMMYNORMALMESSAGE_H

#include "NormalMessage.h"

typedef nx_struct DummyNormalMessage {
	nx_uint8_t state[sizeof(NormalMessage)];

} DummyNormalMessage;

inline int32_t DummyNormal_get_sequence_number(const DummyNormalMessage* msg) { return BOTTOM; }
inline int32_t DummyNormal_get_source_id(const DummyNormalMessage* msg) { return BOTTOM; }

#endif // SLP_MESSAGES_DUMMYNORMALMESSAGE_H
