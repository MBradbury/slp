#ifndef SLP_MESSAGES_BEACONMESSAGE_H
#define SLP_MESSAGES_BEACONMESSAGE_H

typedef nx_struct BeaconMessage
{
  nx_uint64_t sequence_number; // unused
  
  nx_uint16_t sender_sink_distance;

} BeaconMessage;

#endif // SLP_MESSAGES_BEACONMESSAGE_H
