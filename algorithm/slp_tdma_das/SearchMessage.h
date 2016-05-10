#ifndef SLP_MESSAGES_SEARCHMESSAGE_H
#define SLP_MESSAGES_SEARCHMESSAGE_H

#include "utils.h"

typedef nx_struct SearchMessage {
    nx_am_addr_t source_id;
    nx_int32_t dist;
    nx_int32_t pr;
} SearchMessage;

inline SequenceNumberWithBottom Search_get_sequence_number(const SearchMessage* msg) { return BOTTOM; }
inline int32_t Search_get_source_id(const SearchMessage* msg) { return msg->source_id; }

#endif /* SLP_MESSAGES_SEARCHMESSAGE_H */
