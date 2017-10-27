#ifndef SLP_MESSAGES_REPAIRMESSAGE_H
#define SLP_MESSAGES_REPAIRMESSAGE_H

#include "utils.h"

//TODO: Don't need to send the whole path, just source_addr

typedef nx_struct RepairMessage {
    nx_am_addr_t source_id;
    nx_uint16_t source_path_order;
    nx_uint16_t distance;
    nx_am_addr_t path[MAX_REPAIR_PATH_LENGTH];
} RepairMessage;

inline SequenceNumberWithBottom Repair_get_sequence_number(const RepairMessage* msg) { return BOTTOM; }
inline am_addr_t Repair_get_source_id(const RepairMessage* msg) { return msg->source_id; }

#endif /* SLP_MESSAGES_REPAIRMESSAGE_H */
