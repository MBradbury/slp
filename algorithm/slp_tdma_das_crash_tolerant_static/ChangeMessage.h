#ifndef SLP_MESSAGES_CHANGEMESSAGE_H
#define SLP_MESSAGES_CHANGEMESSAGE_H

#include "utils.h"

typedef nx_struct ChangeMessage {
    nx_int32_t n_slot;
    nx_int32_t len_d;
    nx_am_addr_t a_node;
} ChangeMessage;

inline SequenceNumberWithBottom Change_get_sequence_number(const ChangeMessage* msg) { return BOTTOM; }
inline am_addr_t Change_get_source_id(const ChangeMessage* msg) { return AM_BROADCAST_ADDR; }

#endif /* SLP_MESSAGES_CHANGEMESSAGE_H */
