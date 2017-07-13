#ifndef SLP_MESSAGES_CRASHMESSAGE_H
#define SLP_MESSAGES_CRASHMESSAGE_H

typedef nx_struct CrashMessage {
} CrashMessage;

inline SequenceNumberWithBottom Crash_get_sequence_number(const CrashMessage* msg) { return BOTTOM; }
inline int32_t Crash_get_source_id(const CrashMessage* msg) { return BOTTOM; }

#endif /* SLP_MESSAGES_CRASHMESSAGE_H */
