#ifndef SLP_MESSAGES_SEARCHMESSAGE_H
#define SLP_MESSAGES_SEARCHMESSAGE_H

#include "utils.h"

typedef nx_struct SearchMessage {
    nx_int32_t dist;
    nx_am_addr_t a_node;
} SearchMessage;

inline SequenceNumberWithBottom Search_get_sequence_number(const SearchMessage* msg) { return BOTTOM; }
inline int32_t Search_get_source_id(const SearchMessage* msg) { return BOTTOM; }

#endif /* SLP_MESSAGES_SEARCHMESSAGE_H */
