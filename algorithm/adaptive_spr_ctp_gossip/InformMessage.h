#ifndef SLP_MESSAGES_INFORMMESSAGE_H
#define SLP_MESSAGES_INFORMMESSAGE_H

#include "Constants.h"

typedef nx_struct InformMessage
{
	nx_uint16_t source_distance;

	nx_am_addr_t source_id;

} InformMessage;

inline SequenceNumberWithBottom Inform_get_sequence_number(const InformMessage* msg) { return UNKNOWN_SEQNO; }
inline am_addr_t Inform_get_source_id(const InformMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_INFORMMESSAGE_H
