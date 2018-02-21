#ifndef SLP_MESSAGES_POLLMESSAGE_H
#define SLP_MESSAGES_POLLMESSAGE_H

#include "HopDistance.h"

typedef nx_struct
{
  nx_hop_distance_t sink_distance_of_sender;
  nx_hop_distance_t source_distance_of_sender;

} PollMessage;

inline SequenceNumberWithBottom Poll_get_sequence_number(const PollMessage* msg) { return BOTTOM; }
inline am_addr_t Poll_get_source_id(const PollMessage* msg) { return AM_BROADCAST_ADDR; }

#endif // SLP_MESSAGES_POLLMESSAGE_H
