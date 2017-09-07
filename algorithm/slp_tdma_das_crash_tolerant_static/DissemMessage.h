#ifndef SLP_MESSAGES_DISSEMMESSAGE_H
#define SLP_MESSAGES_DISSEMMESSAGE_H

#include "utils.h"

typedef nx_struct DissemMessage {
    OnehopList N;
    nx_uint8_t normal;
    nx_am_addr_t parent;
    nx_uint16_t hop;
} DissemMessage;

inline SequenceNumberWithBottom Dissem_get_sequence_number(const DissemMessage* msg) { return BOTTOM; }
inline int32_t Dissem_get_source_id(const DissemMessage* msg) { return BOTTOM; }

#endif /* SLP_MESSAGES_DISSEMMESSAGE_H */
