#include "TimeSyncMsg.h"

//FTSP parameters
#define TIMESYNC_ENTRY_VALID_LIMIT 4
#define TIMESYNC_ENTRY_SEND_LIMIT 1

module TDMAImplP
{
	provides interface TDMA;

    provides interface Init;

	uses interface Timer<TMilli> as DissemTimer;
	uses interface Timer<TMilli> as PreSlotTimer;
    uses interface Timer<TMilli> as SlotTimer;
    uses interface Timer<TMilli> as PostSlotTimer;
    uses interface Timer<TMilli> as TimesyncTimer;

    uses interface MetricLogging;
    uses interface NodeType;

    uses interface TimeSyncMode;
    uses interface TimeSyncNotify;
    uses interface GlobalTime<TMilli>;
}
implementation
{
	uint16_t slot;
	bool slot_active;
    bool timesync_sent;
    int32_t timesync_offset;

    command error_t Init.init()
    {
        slot = BOT;
        slot_active = FALSE;
        timesync_sent = FALSE;
        timesync_offset = 0;

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
        call TimeSyncMode.setMode(TS_USER_MODE);
	}

	event void DissemTimer.fired()
    {
        uint32_t now = call DissemTimer.gett0() + call DissemTimer.getdt();
        timesync_sent = FALSE;
        call TimeSyncMode.setMode(TS_USER_MODE); //XXX: Do this any earlier and it doesn't work

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
        uint32_t now, local_now, global_now;
        uint16_t s;
        local_now = global_now = call PreSlotTimer.gett0() + call PreSlotTimer.getdt();
        if(call GlobalTime.local2Global(&global_now) == FAIL) {
            global_now = local_now;
        }

        //XXX: Potentially 'now' could negatively wrap-around
        now = local_now - (global_now - local_now + timesync_offset);
        timesync_offset = local_now - global_now;

        s = (slot == BOT) ? TDMA_NUM_SLOTS : slot;
        call SlotTimer.startOneShotAt(now, (s * SLOT_PERIOD_MS));
    }

    event void SlotTimer.fired()
    {
        uint32_t now = call SlotTimer.gett0() + call SlotTimer.getdt();
        slot_active = TRUE;

        signal TDMA.slot_started();

        call PostSlotTimer.startOneShotAt(now, SLOT_PERIOD_MS);
    }

    event void PostSlotTimer.fired()
    {
        uint32_t now, local_now, global_now;
        uint16_t s;
        local_now = global_now = call PostSlotTimer.gett0() + call PostSlotTimer.getdt();
        if(call GlobalTime.local2Global(&global_now) == FAIL) {
            global_now = local_now;
        }

        //XXX: Potentially 'now' could negatively wrap-around
        now = local_now - (global_now - local_now + timesync_offset);
        timesync_offset = local_now - global_now;

        s = (slot == BOT) ? TDMA_NUM_SLOTS : slot;
        signal TDMA.slot_finished();
        slot_active = FALSE;
#if TDMA_TIMESYNC && TIMESYNC_PERIOD_MS > 0
        call TimesyncTimer.startOneShotAt(now, (TDMA_NUM_SLOTS - (s-1)) * SLOT_PERIOD_MS);
#else
        call DissemTimer.startOneShotAt(now, (TDMA_NUM_SLOTS - (s-1)) * SLOT_PERIOD_MS);
#endif
    }

    event void TimesyncTimer.fired()
    {
#if TDMA_TIMESYNC && TIMESYNC_PERIOD_MS > 0
        uint32_t now = call TimesyncTimer.gett0() + call TimesyncTimer.getdt();

        if(call NodeType.is_node_sink()) {
            timesync_sent = TRUE;
            call TimeSyncMode.send();
        }
        call DissemTimer.startOneShotAt(now, TIMESYNC_PERIOD_MS);
#endif
    }

    event void TimeSyncNotify.msg_sent() {
        return;
    }

    event void TimeSyncNotify.msg_received() {
#if TDMA_TIMESYNC && TIMESYNC_PERIOD_MS > 0
        if(!timesync_sent) {
            timesync_sent = TRUE;
            call TimeSyncMode.send();
        }
#endif
    }
}
