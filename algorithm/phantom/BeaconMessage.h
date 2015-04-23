#ifndef SLP_MESSAGES_BEACONMESSAGE_H
#define SLP_MESSAGES_BEACONMESSAGE_H

typedef nx_struct BeaconMessage
{
  nx_uint64_t sequence_number; // unused
  nx_am_addr_t source_id; // unused
  
  nx_int16_t sink_distance_of_sender;

} BeaconMessage;

#endif // SLP_MESSAGES_BEACONMESSAGE_H
