generic module TDMAMultiSlotImplP(uint8_t NODE_SLOTS)
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
    const uint8_t total_slots = NODE_SLOTS;
    uint16_t slots[NODE_SLOTS];
    uint8_t active_slot;
    bool slot_active;

    uint16_t label;

    command error_t Init.init()
    {
        int i;
        for(i = 0; i < total_slots; i++) slots[i] = UINT16_MAX;
        active_slot = UINT8_MAX;
        slot_active = FALSE;

        return SUCCESS;
    }

    command uint8_t TDMAMultiSlot.get_total_slots()
    {
        return total_slots;
    }

    command error_t TDMAMultiSlot.set_slot(uint8_t num, uint16_t new_slot)
    {
        if (num < total_slots)
        {
            const uint16_t old_slot = slots[num];
            slots[num] = new_slot;
            signal TDMAMultiSlot.slot_changed(num, old_slot, new_slot);
            call MetricLogging.log_metric_node_slot_change(old_slot, new_slot);
        }
        else
        {
            return FAIL;
        }

        return SUCCESS;
    }

    command uint16_t TDMAMultiSlot.get_slot(uint8_t num)
    {
        if (num < total_slots)
        {
            return slots[num];
        }
        else
        {
            return UINT16_MAX;
        }
    }

    command uint16_t TDMAMultiSlot.get_current_slot()
    {
        if(active_slot == UINT8_MAX) return 0;
        return slots[active_slot];
    }

    command uint16_t TDMAMultiSlot.get_next_slot()
    {
        uint16_t current_slot = call TDMAMultiSlot.get_current_slot();
        uint16_t next_slot = UINT16_MAX;
        int i;
        current_slot = (current_slot == UINT16_MAX) ? 0 : current_slot;
        for(i = 0; i < total_slots; i++)
        {
            if (slots[i] == UINT16_MAX) continue;
            else if (slots[i] > current_slot && slots[i] < next_slot) next_slot = slots[i];
        }
        return (next_slot == UINT16_MAX) ? 0 : next_slot;
    }

    void advance_slot()
    {
        uint16_t current_slot = call TDMAMultiSlot.get_current_slot();
        uint16_t next_slot = UINT16_MAX;
        uint8_t idx = UINT8_MAX;
        int i;
        current_slot = (current_slot == UINT16_MAX) ? 0 : current_slot;
        for(i = 0; i < total_slots; i++)
        {
            if (slots[i] == UINT16_MAX) continue;
            else if (slots[i] > current_slot && slots[i] < next_slot)
            {
                next_slot = slots[i];
                idx = i;
            }
        }
        active_slot = idx;
        /*label = slots[active_slot];*/
        label = slots[0];
    }

    command bool TDMAMultiSlot.is_slot_active()
    {
        return slot_active;
    }

    command bool TDMAMultiSlot.is_dissem_next()
    {
        return (active_slot == UINT8_MAX);
    }

    command void TDMAMultiSlot.start()
    {
        call DissemTimer.startOneShot(DISSEM_PERIOD_MS);
    }

    event void DissemTimer.fired()
    {
        const uint32_t now = call LocalTime.get();

        if (signal TDMAMultiSlot.dissem_fired())
        {
            call NonSlotTimer.startOneShotAt(now, DISSEM_PERIOD_MS);
        }
        else
        {
            call DissemTimer.startOneShotAt(now, DISSEM_PERIOD_MS);
        }
    }

    event void SlotTimer.fired()
    {
        const uint32_t now = call LocalTime.get();
        slot_active = TRUE;

        signal TDMAMultiSlot.slot_started(active_slot);

        call NonSlotTimer.startOneShotAt(now, SLOT_PERIOD_MS);
    }

    event void NonSlotTimer.fired()
    {
        const uint32_t now = call LocalTime.get();
        const uint16_t current_slot = call TDMAMultiSlot.get_current_slot();
        const uint16_t next_slot = call TDMAMultiSlot.get_next_slot();

        if(current_slot != 0) {
            signal TDMAMultiSlot.slot_finished(active_slot);
            slot_active = FALSE;
        }

        //Advance the slot
        advance_slot();

        if(next_slot == 0) {
            uint16_t s = TDMA_NUM_SLOTS - current_slot;
            call DissemTimer.startOneShotAt(now, s * SLOT_PERIOD_MS);
        }
        else {
            uint16_t s;
            if(current_slot == 0) {
                s = next_slot;
            }
            else {
                s = next_slot - (current_slot + 1);
            }
            call SlotTimer.startOneShotAt(now, s* SLOT_PERIOD_MS);
        }
    }
}

