#ifndef SLP_MESSAGES_DUMMYNORMALMESSAGE_H
#define SLP_MESSAGES_DUMMYNORMALMESSAGE_H

typedef nx_struct DummyNormalMessage {
  //nx_uint16_t source_distance;
  nx_int16_t sender_sink_distance;
  //nx_uint16_t min_sink_source_distance;

  nx_int16_t sender_min_source_distance;

} DummyNormalMessage;

inline int32_t DummyNormal_get_sequence_number(const DummyNormalMessage* msg) { return BOTTOM; }
inline int32_t DummyNormal_get_source_id(const DummyNormalMessage* msg) { return BOTTOM; }

#endif // SLP_MESSAGES_DUMMYNORMALMESSAGE_H
