#ifndef SLP_MESSAGES_BEACONMESSAGE_H
#define SLP_MESSAGES_BEACONMESSAGE_H

typedef nx_struct BeaconMessage
{
  nx_int16_t landmark_distance_of_sender;

} BeaconMessage;

inline SequenceNumberWithBottom Beacon_get_sequence_number(const BeaconMessage* msg) { return BOTTOM; }
inline int32_t Beacon_get_source_id(const BeaconMessage* msg) { return BOTTOM; }

#endif // SLP_MESSAGES_BEACONMESSAGE_H
