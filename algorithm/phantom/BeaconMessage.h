#ifndef SLP_MESSAGES_BEACONMESSAGE_H
#define SLP_MESSAGES_BEACONMESSAGE_H

#include "HopDistance.h"

typedef nx_struct BeaconMessage
{
  nx_hop_distance_t landmark_distance_of_sender;

  nx_uint8_t req;

} BeaconMessage;

inline SequenceNumberWithBottom Beacon_get_sequence_number(const BeaconMessage* msg) { return BOTTOM; }
inline am_addr_t Beacon_get_source_id(const BeaconMessage* msg) { return AM_BROADCAST_ADDR; }

#endif // SLP_MESSAGES_BEACONMESSAGE_H
