#ifndef SLP_MESSAGES_SETUPMESSAGE_H
#define SLP_MESSAGES_SETUPMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct SetupMessage {

	nx_uint16_t root_distance;

	// The id of the node that sent this message
	nx_am_addr_t proximate_source_id;

	nx_uint8_t sender_is_root;

} SetupMessage;

inline SequenceNumberWithBottom Setup_get_sequence_number(const SetupMessage* msg) { return UNKNOWN_SEQNO; }
inline am_addr_t Setup_get_source_id(const SetupMessage* msg) { return AM_BROADCAST_ADDR; }

#endif // SLP_MESSAGES_SETUPMESSAGE_H
