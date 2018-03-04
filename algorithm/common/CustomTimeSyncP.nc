
#include <inttypes.h>

#include <message.h>

#include "CustomTimeSync.h"

generic module CustomTimeSyncP(typedef SyncMessage)
{
    provides interface CustomTimeSync<SyncMessage>;
    provides interface CustomTime;

    uses interface Boot;
    uses interface LocalTime<TMilli>;

    uses interface Packet;
    uses interface PacketTimeStamp<TMilli,uint32_t>;
}
implementation
{
    #define MAX_ENTRIES 8
    #define ENTRY_AGE_LIMIT 0x07FFFFFFFL

    typedef struct SyncEntry {
        bool valid;
        /*am_addr_t id;*/
        uint32_t time_added;
        int64_t time_diff;
    } SyncEntry_t;

    SyncEntry_t entries[MAX_ENTRIES];

    int64_t average_time_diff;

    void clear_entries() {
        uint8_t i;
        for(i = 0; i < MAX_ENTRIES; i++) {
            entries[i].valid = FALSE;
        }

        average_time_diff = 0;
    }

    //Returns the oldest element in entries
    uint8_t remove_old_entries() {
        uint8_t i;
        uint8_t oldest_index = UINT8_MAX;
        uint32_t oldest_time = UINT32_MAX;
        uint32_t now = call LocalTime.get();

        for(i = 0; i < MAX_ENTRIES; i++) {
            if(entries[i].valid && (now - entries[i].time_added) > ENTRY_AGE_LIMIT) {
                entries[i].valid = FALSE;
            }
            if(entries[i].valid && oldest_time > entries[i].time_added) {
                oldest_time = entries[i].time_added;
                oldest_index = i;
            }
        }

        return oldest_index;
    }

    void calculate_average_time_diff() {
        uint8_t i;
        int64_t sum = 0;
        uint8_t count = 0;

        for(i = 0; i < MAX_ENTRIES; i++) {
            if(entries[i].valid) {
                sum += entries[i].time_diff;
                count++;
            }
        }

        if(count > 0) {
            average_time_diff = sum / count;
        }
    }

    error_t add_entry(CustomTimeSyncMessage* msg, uint32_t rcv_timestamp) {
        uint8_t i;
        uint8_t oldest_index;
        uint8_t free_index = UINT8_MAX;

        oldest_index = remove_old_entries();

        for(i = 0; i < MAX_ENTRIES; i++) {
            if(!entries[i].valid) {
                free_index = i;
            }
        }

        if(free_index == UINT8_MAX) {
            if(oldest_index != UINT8_MAX) {
                free_index = oldest_index;
            }
            else {
                simdbg("stderr", "No free index or oldest index (impossible)\n");
                return FAIL;
            }
        }

        entries[free_index].valid = TRUE;
        /*entries[free_index].id = msg->sender_id;*/
        entries[free_index].time_added = rcv_timestamp;
        entries[free_index].time_diff = (int64_t)(msg->global_time) - (int64_t)rcv_timestamp;

        calculate_average_time_diff();

        return SUCCESS;
    }

    uint32_t local_to_global(uint32_t time) {
        return (uint32_t)(time + average_time_diff);
    }

    uint32_t global_to_local(uint32_t time) {
        return (uint32_t)(time - average_time_diff);
    }

    event void Boot.booted() {
        average_time_diff = 0;
        clear_entries();
    }

    command uint32_t CustomTime.local_to_global(uint32_t time) {
        uint32_t g_time = local_to_global(time);
        /*int64_t diff = (int64_t)g_time - (int64_t)time;*/
        /*if(diff > 500 || diff < -500) {*/
            /*simdbg("stdout", "Local=%" PRIu32 ", Global=%" PRIu32 "\n", time, g_time);*/
        /*}*/
        return g_time;
    }

    command uint32_t CustomTime.global_to_local(uint32_t time) {
        return global_to_local(time);
    }

    command uint32_t CustomTime.local_time() {
        return call LocalTime.get();
    }

    command uint32_t CustomTime.global_time() {
        uint32_t g_time = global_to_local(call LocalTime.get());
        /*simdbg("stdout", "Global=%" PRIu32 "\n", g_time);*/
        return g_time;
    }

    command error_t CustomTimeSync.update(message_t* message, uint16_t hops)
    {
        return SUCCESS;
        /*if(call PacketTimeStamp.isValid(message)) {*/
            /*uint32_t rcv_timestamp = call PacketTimeStamp.timestamp(message);*/
            /*CustomTimeSyncMessage* sync_message = call Packet.getPayload(message, sizeof(CustomTimeSyncMessage));*/
            /*if(hops != UINT8_MAX && hops >= sync_message->hops) {*/
                /*add_entry(sync_message, rcv_timestamp);*/
                /*return SUCCESS;*/
            /*}*/
        /*}*/
        /*else {*/
            /*simdbg("stdout", "PacketTimeStamp was invalid\n");*/
        /*}*/
        /*return FAIL;*/
    }

    command void CustomTimeSync.init_message(SyncMessage* message, uint16_t hops)
    {
        return;
        /*CustomTimeSyncMessage* msg = (CustomTimeSyncMessage*)message;*/
        /*[>msg->sender_id = TOS_NODE_ID;<]*/
        /*[>msg->local_time = call CustomTime.local_time();<]*/
        /*[>msg->global_time = call CustomTime.local_to_global(msg->local_time);<]*/
        /*msg->global_time = call CustomTime.global_time();*/
        /*msg->hops = hops;*/
    }

}
