#ifndef SLP_MESSAGES_BEACONMESSAGE_H
#define SLP_MESSAGES_BEACONMESSAGE_H

#include "Constants.h"
#include "NormalMessage.h"

typedef nx_struct BeaconMessage
{
	nx_int16_t neighbour_min_source_distance;

	nx_int16_t sink_distance;

} BeaconMessage;

inline SequenceNumberWithBottom Beacon_get_sequence_number(const BeaconMessage* msg) { return BOTTOM; }
inline am_addr_t Beacon_get_source_id(const BeaconMessage* msg) { return AM_BROADCAST_ADDR; }

#endif // SLP_MESSAGES_BEACONMESSAGE_H
