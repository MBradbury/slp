#ifndef SLP_MESSAGES_NORMALMESSAGE_H
#define SLP_MESSAGES_NORMALMESSAGE_H

#include "SequenceNumber.h"
#include "HopDistance.h"

typedef enum {
	NORMAL_ROUTE_AVOID_SINK = 0,
	NORMAL_ROUTE_TO_SINK = 1,
  NORMAL_ROUTE_FROM_SINK = 2,
  NORMAL_ROUTE_AVOID_SINK_BACKTRACK = 3,
  NORMAL_ROUTE_AVOID_SINK_1_CLOSER = 4,

} NormalMessageStages;

typedef nx_struct {
  NXSequenceNumber sequence_number;

  // How many milliseconds elapsed between this message
  // being added to the queue on the sender and the sender
  // actually sending it.
  nx_uint32_t time_taken_to_send;

  // The number of hops that this message
  // has travelled from the source. 
  nx_hop_distance_t source_distance;
  nx_hop_distance_t sink_source_distance;

  nx_hop_distance_t source_distance_of_sender;

  // The id of the node that sent this message
  nx_am_addr_t source_id;

  nx_uint16_t delay;

  nx_uint8_t stage;

} NormalMessage;

inline SequenceNumberWithBottom Normal_get_sequence_number(const NormalMessage* msg) { return msg->sequence_number; }
inline int32_t Normal_get_source_id(const NormalMessage* msg) { return msg->source_id; }

#endif // SLP_MESSAGES_NORMALMESSAGE_H
