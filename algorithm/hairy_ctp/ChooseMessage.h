#ifndef SLP_MESSAGES_CHOOSEMESSAGE_H
#define SLP_MESSAGES_CHOOSEMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct ChooseMessage {

	nx_uint8_t at_end;

} ChooseMessage;

inline SequenceNumberWithBottom Choose_get_sequence_number(const ChooseMessage* msg) { return UNKNOWN_SEQNO; }
inline int32_t Choose_get_source_id(const ChooseMessage* msg) { return BOTTOM; }

#endif // SLP_MESSAGES_CHOOSEMESSAGE_H
