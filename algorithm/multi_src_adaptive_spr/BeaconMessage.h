#ifndef SLP_MESSAGES_BEACONMESSAGE_H
#define SLP_MESSAGES_BEACONMESSAGE_H

#include "Constants.h"
#include "NormalMessage.h"

typedef nx_struct BeaconMessage
{
	nx_uint16_t node[SLP_MAX_NUM_SOURCES];
	nx_int16_t distance[SLP_MAX_NUM_SOURCES];
	nx_uint16_t count;

} BeaconMessage;

inline int64_t Beacon_get_sequence_number(const BeaconMessage* msg) { return BOTTOM; }
inline int32_t Beacon_get_source_id(const BeaconMessage* msg) { return BOTTOM; }

#endif // SLP_MESSAGES_BEACONMESSAGE_H
