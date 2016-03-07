#ifndef SLP_MESSAGES_WAVEMESSAGE_H
#define SLP_MESSAGES_WAVEMESSAGE_H

#include "utils.h"

typedef nx_struct WaveMessage {
    nx_am_addr_t source_id;
    nx_uint16_t slot;
    nx_uint16_t hop;
    IDList neighbours;
} WaveMessage;

inline int64_t Wave_get_sequence_number(const WaveMessage* msg) { return BOTTOM; }
inline int32_t Wave_get_source_id(const WaveMessage* msg) { return msg->source_id; }

#endif /* SLP_MESSAGES_WAVEMESSAGE_H */
