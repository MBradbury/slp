#ifndef SLP_MESSAGES_DISSEMMESSAGE_H
#define SLP_MESSAGES_DISSEMMESSAGE_H

#include "utils.h"

typedef nx_struct DissemMessage {
    OnehopList N;
    nx_uint8_t normal;
    nx_am_addr_t parent;
} DissemMessage;

inline SequenceNumberWithBottom Dissem_get_sequence_number(const DissemMessage* msg) { return BOTTOM; }
inline am_addr_t Dissem_get_source_id(const DissemMessage* msg) { return AM_BROADCAST_ADDR; }

#endif /* SLP_MESSAGES_DISSEMMESSAGE_H */
