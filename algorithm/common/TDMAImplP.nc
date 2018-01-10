
module TDMAImplP
{
	provides interface TDMA;

    provides interface Init;

	uses interface LocalTime<TMilli>;

	uses interface Timer<TMilli> as DissemTimer;
	uses interface Timer<TMilli> as PreSlotTimer;
    uses interface Timer<TMilli> as SlotTimer;
    uses interface Timer<TMilli> as PostSlotTimer;

    uses interface MetricLogging;
}
implementation
{
	uint16_t slot;
	bool slot_active;

    command error_t Init.init()
    {
        slot = BOT;
        slot_active = FALSE;

        return SUCCESS;
    }

	command void TDMA.set_slot(uint16_t new_slot)
	{
		const uint16_t old_slot = slot;
		slot = new_slot;
		signal TDMA.slot_changed(old_slot, new_slot);
		call MetricLogging.log_metric_node_slot_change(old_slot, new_slot);
	}

	command uint16_t TDMA.get_slot()
	{
		return slot;
	}

	command bool TDMA.is_slot_active()
	{
		return slot_active;
	}

	command void TDMA.start()
	{
		call DissemTimer.startOneShot(DISSEM_PERIOD_MS);
	}

	event void DissemTimer.fired()
    {
        const uint32_t now = call DissemTimer.gett0() + call DissemTimer.getdt();
        
        if (signal TDMA.dissem_fired())
        {
        	call PreSlotTimer.startOneShotAt(now, DISSEM_PERIOD_MS);
        }
        else
        {
        	call DissemTimer.startOneShotAt(now, DISSEM_PERIOD_MS);
        }
    }

	event void PreSlotTimer.fired()
    {
        const uint32_t now = call PreSlotTimer.gett0() + call PreSlotTimer.getdt();
        const uint16_t s = (slot == BOT) ? TDMA_NUM_SLOTS : slot;
        call SlotTimer.startOneShotAt(now, s * SLOT_PERIOD_MS);
    }

    event void SlotTimer.fired()
    {
        const uint32_t now = call SlotTimer.gett0() + call SlotTimer.getdt();
        slot_active = TRUE;

        signal TDMA.slot_started();

        call PostSlotTimer.startOneShotAt(now, SLOT_PERIOD_MS);
    }

    event void PostSlotTimer.fired()
    {
        const uint32_t now = call PostSlotTimer.gett0() + call PostSlotTimer.getdt();
        const uint16_t s = (slot == BOT) ? TDMA_NUM_SLOTS : slot;
        signal TDMA.slot_finished();
        slot_active = FALSE;
        call DissemTimer.startOneShotAt(now, (TDMA_NUM_SLOTS - (s-1)) * SLOT_PERIOD_MS);
    }
}
