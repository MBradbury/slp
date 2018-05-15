#ifndef CUSTOM_TIMESYNC_H
#define CUSTOM_TIMESYNC_H

typedef nx_struct CustomTimeSyncMessage {
    //nx_am_addr_t sender_id;
    //nx_uint32_t local_time;
    nx_uint32_t global_time;
    nx_uint16_t hops;
} CustomTimeSyncMessage;

//CUSTOM_TIMESYNC_MSG_DATA must be declared as the first member of the sync message structure

#define CUSTOM_TIMESYNC_MSG_DATA CustomTimeSyncMessage custom_timesync

#endif /* CUSTOM_TIMESYNC_H */
