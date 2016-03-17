#ifndef SLP_MESSAGES_DISSEMMESSAGE_H
#define SLP_MESSAGES_DISSEMMESSAGE_H

#include "utils.h"

typedef nx_struct DissemMessage {
    nx_am_addr_t source_id;
    NeighbourList N;
} DissemMessage;

inline int64_t Dissem_get_sequence_number(const DissemMessage* msg) { return BOTTOM; }
inline int32_t Dissem_get_source_id(const DissemMessage* msg) { return msg->source_id; }

#endif /* SLP_MESSAGES_DISSEMMESSAGE_H */
