#ifndef SLP_MESSAGES_MOVEMESSAGE_H
#define SLP_MESSAGES_MOVEMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct MoveMessage {

} MoveMessage;

inline SequenceNumberWithBottom Move_get_sequence_number(const MoveMessage* msg) { return BOTTOM; }
inline int32_t Move_get_source_id(const MoveMessage* msg) { return BOTTOM; }

#endif // SLP_MESSAGES_MOVEMESSAGE_H
