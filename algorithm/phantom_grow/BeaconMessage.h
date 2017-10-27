#ifndef SLP_MESSAGES_BEACONMESSAGE_H
#define SLP_MESSAGES_BEACONMESSAGE_H

typedef nx_struct BeaconMessage
{
} BeaconMessage;

inline SequenceNumberWithBottom Beacon_get_sequence_number(const BeaconMessage* msg) { return BOTTOM; }
inline am_addr_t Beacon_get_source_id(const BeaconMessage* msg) { return AM_BROADCAST_ADDR; }

#endif // SLP_MESSAGES_BEACONMESSAGE_H
