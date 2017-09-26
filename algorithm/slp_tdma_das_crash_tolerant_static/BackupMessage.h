#ifndef SLP_MESSAGES_BACKUPMESSAGE_H
#define SLP_MESSAGES_BACKUPMESSAGE_H

#include "utils.h"

typedef nx_struct BackupMessage {
    nx_uint16_t max_slot;
    nx_uint16_t min_slot;
    nx_am_addr_t next_path_node;
} BackupMessage;

inline SequenceNumberWithBottom Backup_get_sequence_number(const BackupMessage* msg) { return BOTTOM; }
inline int32_t Backup_get_source_id(const BackupMessage* msg) { return BOTTOM; }

#endif /* SLP_MESSAGES_BACKUPMESSAGE_H */
