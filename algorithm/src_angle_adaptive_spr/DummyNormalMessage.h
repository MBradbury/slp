#ifndef SLP_MESSAGES_DUMMYNORMALMESSAGE_H
#define SLP_MESSAGES_DUMMYNORMALMESSAGE_H

typedef nx_struct DummyNormalMessage {
  //nx_uint16_t source_distance;
  nx_int16_t sender_sink_distance;

  nx_int16_t sender_min_source_distance;

  nx_int16_t flood_limit;

} DummyNormalMessage;

inline SequenceNumberWithBottom DummyNormal_get_sequence_number(const DummyNormalMessage* msg) { return BOTTOM; }
inline am_addr_t DummyNormal_get_source_id(const DummyNormalMessage* msg) { return AM_BROADCAST_ADDR; }

#endif // SLP_MESSAGES_DUMMYNORMALMESSAGE_H
