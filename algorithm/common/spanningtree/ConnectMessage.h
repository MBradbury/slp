#ifndef SLP_MESSAGES_CONNECTMESSAGE_H
#define SLP_MESSAGES_CONNECTMESSAGE_H

#include "SequenceNumber.h"

typedef nx_struct ConnectMessage {

	nx_uint16_t p;

	// The id of the node that sent this message
	nx_am_addr_t proximate_source_id;

	nx_uint8_t ack_requested;

} ConnectMessage;

inline SequenceNumberWithBottom Connect_get_sequence_number(const ConnectMessage* msg) { return UNKNOWN_SEQNO; }
inline int32_t Connect_get_source_id(const ConnectMessage* msg) { return BOTTOM; }

#endif // SLP_MESSAGES_CONNECTMESSAGE_H
