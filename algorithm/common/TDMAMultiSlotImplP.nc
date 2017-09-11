/*#include "slp_static_assert.h"*/

#define BAD_SLOT UINT16_MAX
#define BAD_SLOT_INDEX UINT8_MAX

#define DISSEM_SLOT 0
#define DISSEM_SLOT_INDEX (UINT8_MAX - 1)

generic module TDMAMultiSlotImplP(uint8_t TOTAL_SLOTS)
{
    provides interface TDMAMultiSlot;

    provides interface Init;

    uses interface LocalTime<TMilli>;

    uses interface Timer<TMilli> as DissemTimer;
    uses interface Timer<TMilli> as SlotTimer;
    uses interface Timer<TMilli> as NonSlotTimer;

    uses interface MetricLogging;
}
implementation
{
    uint16_t slots[TOTAL_SLOTS];
    uint8_t active_slot_index;
    bool slot_active;

    uint16_t label;

    command error_t Init.init(void)
    {
        uint8_t i;
        /*STATIC_ASSERT_MSG(TOTAL_SLOTS < UINT8_MAX - 1, total_slots_too_large);*/
        for(i = 0; i < TOTAL_SLOTS; i++) {
            slots[i] = BAD_SLOT;
        }
        active_slot_index = DISSEM_SLOT_INDEX;
        slot_active = FALSE;
        label = DISSEM_SLOT;
        return SUCCESS;
    }

    command uint16_t TDMAMultiSlot.bad_slot(void)
    {
        return BAD_SLOT;
    }

    command uint16_t TDMAMultiSlot.dissem_slot(void)
    {
        return DISSEM_SLOT;
    }

    command uint8_t TDMAMultiSlot.get_total_slots(void)
    {
        return TOTAL_SLOTS;
    }

    command uint16_t TDMAMultiSlot.get_slot(uint8_t num)
    {
        assert(num < TOTAL_SLOTS);
        return slots[num];
    }

    command error_t TDMAMultiSlot.set_slot(uint8_t num, uint16_t new_slot)
    {
        assert(num < TOTAL_SLOTS);
        if(new_slot > 0) {
            uint16_t old_slot = slots[num];
            slots[num] = new_slot;
            signal TDMAMultiSlot.slot_changed(num, old_slot, new_slot);
            //TODO Change slot change logging to include slot index
            call MetricLogging.log_metric_node_slot_change(old_slot, new_slot);
            return SUCCESS;
        }
        return FAIL;
    }

    command uint16_t TDMAMultiSlot.get_current_slot(void)
    {
        if(active_slot_index == BAD_SLOT_INDEX) {
            return BAD_SLOT;
        }
        else if(active_slot_index == DISSEM_SLOT_INDEX) {
            return DISSEM_SLOT;
        }
        else {
            return slots[active_slot_index];
        }
    }

    uint8_t get_next_slot_index(void)
    {
        const uint16_t current_slot = call TDMAMultiSlot.get_current_slot();
        uint16_t next_slot = BAD_SLOT;
        uint8_t next_slot_idx = BAD_SLOT_INDEX;
        uint8_t i;
        for(i = 0; i < TOTAL_SLOTS; i++) {
            if(slots[i] == BAD_SLOT) continue;
            else if(slots[i] > current_slot && slots[i] < next_slot) {
                next_slot = slots[i];
                next_slot_idx = i;
            }
        }
        return (next_slot_idx == BAD_SLOT_INDEX) ? DISSEM_SLOT_INDEX : next_slot_idx;
    }

    command uint16_t TDMAMultiSlot.get_next_slot(void)
    {
        uint8_t next_slot_idx = get_next_slot_index();
        return (next_slot_idx == DISSEM_SLOT_INDEX) ? DISSEM_SLOT : slots[next_slot_idx];
    }

    command bool TDMAMultiSlot.is_slot_active(void)
    {
        return slot_active;
    }

    command bool TDMAMultiSlot.is_dissem_next(void)
    {
        return (call TDMAMultiSlot.get_next_slot() == DISSEM_SLOT);
    }

    command bool TDMAMultiSlot.is_slot_good(uint8_t num)
    {
        assert(num < TOTAL_SLOTS);
        return (slots[num] != BAD_SLOT);
    }

    command void TDMAMultiSlot.start(void)
    {
        call DissemTimer.startOneShot(DISSEM_PERIOD_MS);
    }

    event void DissemTimer.fired(void)
    {
        const uint32_t now = call LocalTime.get();

        if(signal TDMAMultiSlot.dissem_fired()) {
            call NonSlotTimer.startOneShotAt(now, DISSEM_PERIOD_MS);
        }
        else {
            call DissemTimer.startOneShotAt(now, DISSEM_PERIOD_MS);
        }
    }

    event void SlotTimer.fired(void)
    {
        const uint32_t now = call LocalTime.get();
        slot_active = TRUE;
        signal TDMAMultiSlot.slot_started(active_slot_index);
        call NonSlotTimer.startOneShotAt(now, SLOT_PERIOD_MS);
    }

    void advance_slot(void)
    {
        active_slot_index = get_next_slot_index();
        label = call TDMAMultiSlot.get_next_slot();
    }

    event void NonSlotTimer.fired(void)
    {
        const uint32_t now = call LocalTime.get();
        const uint16_t current_slot = call TDMAMultiSlot.get_current_slot();
        const uint16_t next_slot = call TDMAMultiSlot.get_next_slot();

        if(current_slot != DISSEM_SLOT) {
            slot_active = FALSE;
            signal TDMAMultiSlot.slot_finished(active_slot_index);
        }

        advance_slot();

        if(next_slot == DISSEM_SLOT) {
            if(current_slot == DISSEM_SLOT) {
                call DissemTimer.startOneShotAt(now, TDMA_NUM_SLOTS * SLOT_PERIOD_MS);
            }
            else {
                call DissemTimer.startOneShotAt(now, (TDMA_NUM_SLOTS - current_slot) * SLOT_PERIOD_MS);
            }
        }
        else {
            if(current_slot == DISSEM_SLOT) {
                call SlotTimer.startOneShotAt(now, (next_slot - 1) * SLOT_PERIOD_MS);
            }
            else {
                //XXX This line is untested
                call SlotTimer.startOneShotAt(now, (next_slot - current_slot) * SLOT_PERIOD_MS);
            }
        }
    }
}
