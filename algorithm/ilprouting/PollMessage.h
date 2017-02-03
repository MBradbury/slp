#ifndef SLP_MESSAGES_POLLMESSAGE_H
#define SLP_MESSAGES_POLLMESSAGE_H

typedef nx_struct
{
  nx_int16_t sink_distance_of_sender;
  nx_int16_t source_distance_of_sender;

} PollMessage;

inline SequenceNumberWithBottom Poll_get_sequence_number(const PollMessage* msg) { return BOTTOM; }
inline int32_t Poll_get_source_id(const PollMessage* msg) { return BOTTOM; }

#endif // SLP_MESSAGES_POLLMESSAGE_H
