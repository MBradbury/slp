#ifndef SLP_MESSAGES_BEACONMESSAGE_H
#define SLP_MESSAGES_BEACONMESSAGE_H

typedef nx_struct BeaconMessage {
    nx_am_addr_t source_id;
} BeaconMessage;

inline int64_t Beacon_get_sequence_number(const BeaconMessage* msg) { return 0; }
inline int32_t Beacon_get_source_id(const BeaconMessage* msg) { return msg->source_id; }

#endif /* SLP_MESSAGES_BEACONMESSAGE_H */
