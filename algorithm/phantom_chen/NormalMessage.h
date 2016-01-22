#ifndef SLP_MESSAGES_NORMALMESSAGE_H
#define SLP_MESSAGES_NORMALMESSAGE_H

#include "Common.h"
#include "SequenceNumber.h"

typedef nx_struct NormalMessage
{
	nx_uint64_t sequence_number;
	nx_uint16_t source_id;
	nx_uint16_t target;
	nx_uint16_t walk_distance_remaining;
	nx_uint16_t source_distance;
	nx_uint16_t flip_coin;

} NormalMessage;

inline int64_t Normal_get_sequence_number(const NormalMessage* msg) { return msg->sequence_number; }
inline int32_t Normal_get_source_id(const NormalMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_NORMALMESSAGE_H
