
/*#include <message.h>*/

#include "CustomTimeSync.h"

generic module CustomTimeSyncP(typedef SyncMessage)
{
    provides interface CustomTimeSync<SyncMessage>;
    provides interface CustomTime;
    provides interface Init;

    uses interface LocalTime<TMilli>;
}
implementation
{
#define MAX_ENTRIES 8
#define ENTRY_VALID_LIMIT 1
#define ENTRY_THROWOUT_LIMIT 500
#define ENTRY_AGE_LIMIT 0x07FFFFFFFL
#define MAX_ADD_ERRORS 3

    typedef struct SyncEntry {
        bool valid;
        uint32_t local_time;
        int32_t time_offset; //global_time - local_time
    } SyncEntry_t;

    SyncEntry_t entries[MAX_ENTRIES];
    uint8_t num_entries;

    float skew;
    uint32_t local_average;
    int32_t offset_average;

    uint8_t add_entry_errors;

    void clear_entries() {
        int i;
        for(i = 0; i < MAX_ENTRIES; i++) {
            entries[i].valid = FALSE;
        }
        num_entries = 0;
    }

    bool is_synced() {
        return num_entries >= ENTRY_VALID_LIMIT;
    }

    uint32_t global_to_local(uint32_t time)
    {
        if(is_synced()) {
            uint32_t approx_local_time = time - offset_average;
            return approx_local_time - (int32_t)(skew * (int32_t)(approx_local_time - local_average));
        }
        else {
            return time;
        }
    }

    uint32_t local_to_global(uint32_t time)
    {
        if(is_synced()) {
            return time + offset_average + (int32_t)(skew * (int32_t)(time - local_average));
        }
        else {
            return time;
        }
    }

    //Calculate the values required for further time conversions
    void calculate_conversion() {
        float new_skew;
        uint32_t new_local_average;
        int32_t new_offset_average;
        int32_t local_average_rest = 0;
        int32_t offset_average_rest = 0;

        int64_t local_sum = 0;
        int64_t offset_sum = 0;

        uint8_t i;

        //There are no current entries that are valid if [0] is invalid (I think)
        if(!entries[0].valid) return;

        new_local_average = entries[0].local_time;
        new_offset_average = entries[0].time_offset;

        for(i = 0; i < MAX_ENTRIES; i++) {
            if(entries[i].valid) {
                //This only works because C ISO 1999 defines the sign for modulo the same as the dividend
                local_sum += (int32_t)(entries[i].local_time - new_local_average) / num_entries;
                local_average_rest += (entries[i].local_time - new_local_average) % num_entries;
                offset_sum += (int32_t)(entries[i].time_offset - new_offset_average) / num_entries;
                offset_average_rest += (entries[i].time_offset - new_offset_average) % num_entries;
            }
        }

        new_local_average += local_sum + local_average_rest / num_entries;
        new_offset_average += offset_sum + offset_average_rest / num_entries;

        local_sum = offset_sum = 0;
        for(i = 0; i < MAX_ENTRIES; i++) {
            if(entries[i].valid) {
                int32_t a = entries[i].local_time - new_local_average;
                int32_t b = entries[i].time_offset - new_offset_average;

                local_sum += (int64_t)a * (int64_t)a;
                offset_sum += (int64_t)a * (int64_t)b;
            }
        }

        if(local_sum != 0) {
            new_skew = (float)offset_sum / (float)local_sum;
        }
        else {
            new_skew = skew;
        }

        atomic {
            skew = new_skew;
            offset_average = new_offset_average;
            local_average = new_local_average;
        }

    }

    //Return whether a new conversion should be calculated or not
    error_t add_entry(CustomTimeSyncMessage* msg) {
        uint8_t i;
        int32_t time_error;

        uint32_t ages[MAX_ENTRIES];
        int8_t free_item = -1;
        uint8_t oldest_item = 0;
        uint32_t oldest_time = 0;

        time_error = local_to_global(msg->local_time) - msg->global_time;

        //If error is too large, do not add
        if(is_synced() && (time_error > ENTRY_THROWOUT_LIMIT || time_error < -ENTRY_THROWOUT_LIMIT)) {
            //If too many errors, clear entries and return to unsynced state
            if(++add_entry_errors > MAX_ADD_ERRORS) {
                clear_entries();
            }
            return FAIL;
        }

        //Reset number of errors if an entry is to be added
        add_entry_errors = 0;

        //Invalidate entries which are too old
        for(i = 0; i < MAX_ENTRIES; i++) {
            ages[i] = msg->local_time - entries[i].local_time;
            if(entries[i].valid && ages[i] > ENTRY_AGE_LIMIT) {
                entries[i].valid = FALSE;
                num_entries--;
            }
        }

        //Find free or oldest entry
        for(i = 0; i < MAX_ENTRIES; i++) {
            if(!entries[i].valid) {
                free_item = i;
                break;
            }
            else if(ages[i] > oldest_time) {
                oldest_item = i;
                oldest_time = ages[i];
            }
        }

        //Check if we need to remove oldest item
        if(free_item == -1) {
            free_item == oldest_item;
        }
        else {
            num_entries++;
        }

        entries[free_item].valid = TRUE;
        entries[free_item].local_time = msg->local_time;
        entries[free_item].time_offset = msg->global_time - msg->local_time;

        return SUCCESS;
    }

    /*error_t update_global_time(uint32_t timestamp, SyncMessage* msg, uint16_t hops)*/
    error_t update_global_time(CustomTimeSyncMessage* msg, uint16_t hops)
    {
        /*if(hops >= msg->custom_timesync.hops && msg->custom_timesync.sender_id > TOS_NODE_ID) {*/
        if(hops != UINT8_MAX && hops >= msg->hops) {
            bool success;
            //Only calculate conversion on successful addition
            if((success = add_entry(msg))) {
                calculate_conversion();
            }
            return success;
        }
        return FAIL;
    }

    command error_t Init.init() {
        atomic {
            skew = 0.0f;
            local_average = 0;
            offset_average = 0;

            add_entry_errors = 0;
        }

        clear_entries();

        return SUCCESS;
    }

    command uint32_t CustomTime.local_time() {
        return call LocalTime.get();
    }

    command uint32_t CustomTime.global_time() {
        return local_to_global(call LocalTime.get());
    }

    command uint32_t CustomTime.local_to_global(uint32_t time) {
        return local_to_global(time);
    }

    command uint32_t CustomTime.global_to_local(uint32_t time) {
        return global_to_local(time);
    }

    command error_t CustomTimeSync.update(const SyncMessage* const message, uint16_t hops)
    {
        /*if(call PacketTimeStamp.isValid(message)) {*/
            /*uint32_t timestamp = call PacketTimeStamp.timestamp(message);*/
            /*return update_global_time(timestamp, (SyncMessage*)call Packet.getPayload(message, sizeof(SyncMessage)), hops);*/
        /*}*/
        /*return FAIL;*/
        return update_global_time((CustomTimeSyncMessage*)message, hops);
    }

    command void CustomTimeSync.init_message(SyncMessage* message, uint16_t hops)
    {
        CustomTimeSyncMessage* msg = (CustomTimeSyncMessage*)message;
        msg->sender_id = TOS_NODE_ID;
        msg->local_time = call CustomTime.local_time();
        msg->global_time = call CustomTime.global_time();
        msg->hops = hops;
    }

}
