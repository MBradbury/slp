#include "TimeSyncMsg.h"

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
    uint16_t next_period_slot;
	bool slot_active;
    bool timesync_sent;
    int32_t timesync_offset;

    command error_t Init.init()
    {
        slot = BOT;
        next_period_slot = BOT;
        slot_active = FALSE;
        timesync_sent = FALSE;
        timesync_offset = 0;

        return SUCCESS;
    }

	command void TDMA.set_slot(uint16_t new_slot)
	{
		const uint16_t old_slot = slot;

        if(!((0 < new_slot && new_slot <= TDMA_NUM_SLOTS) || new_slot == BOT))
        {
            ERROR_OCCURRED(ERROR_ASSERT, "FAILED: 0 < %u <= %u || BOT\n", new_slot, TDMA_NUM_SLOTS);
        }

		next_period_slot = new_slot;
		signal TDMA.slot_changed(old_slot, new_slot);
		call MetricLogging.log_metric_node_slot_change(old_slot, new_slot);
	}

    command void TDMA.set_valid_slot(uint16_t new_slot)
    {
        if (new_slot == BOT)
        {
            ERROR_OCCURRED(ERROR_ASSERT, "Tried to set slot to BOT\n");
        }
        call TDMA.set_slot(new_slot);
    }

	command uint16_t TDMA.get_slot()
	{
		/*return slot;*/
        return next_period_slot;
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
        bool dissem_result;

        timesync_sent = FALSE;

        call TimeSyncMode.setMode(TS_USER_MODE); //XXX: Do this any earlier and it doesn't work

        dissem_result = signal TDMA.dissem_fired();
        assert(dissem_result);
        if (dissem_result)
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
        int32_t timesync_overflow;

        local_now = global_now = call PreSlotTimer.gett0() + call PreSlotTimer.getdt();
        if(call GlobalTime.local2Global(&global_now) == FAIL) {
            global_now = local_now;
        }

        slot = next_period_slot;

        s = (slot == BOT) ? TDMA_NUM_SLOTS : slot-1;

        //XXX: Potentially 'now' could negatively wrap-around
        now = local_now - (global_now - local_now + timesync_offset);
        timesync_offset = local_now - global_now;

#ifdef TOSSIM
        assert(now == local_now);
#endif

        //If timesync_offset is too large for the timer, reduce the offset for
        //this step and catch up in another timer
        if((timesync_overflow = local_now - (now + (s * SLOT_PERIOD_MS))) > 0) {
            timesync_offset -= timesync_overflow;
        }

#ifdef TOSSIM
        assert(timesync_offset == 0);
#endif

        if (slot == BOT)
        {
            call DissemTimer.startOneShotAt(now, (s * SLOT_PERIOD_MS));
        }
        else
        {
            call SlotTimer.startOneShotAt(now, (s * SLOT_PERIOD_MS));
        }
    }

#ifdef TOSSIM
    uint32_t prev_slot_time = -1;
    uint16_t prev_slot_slot = -1;
#endif

    event void SlotTimer.fired()
    {
        uint32_t now = call SlotTimer.gett0() + call SlotTimer.getdt();

        slot_active = TRUE;

        ASSERT_MESSAGE(slot != BOT, "Assertion failed %"PRIu16" != %"PRIu16"\n", slot, BOT);

#ifdef TOSSIM
        if (prev_slot_time != -1)
        {
            uint16_t slot_diff = (prev_slot_slot == -1) ? 0 : prev_slot_slot - slot;

            if (call SlotTimer.getNow() - prev_slot_time + (slot_diff * SLOT_PERIOD_MS) !=
                (TDMA_NUM_SLOTS * SLOT_PERIOD_MS + DISSEM_PERIOD_MS))
            {
                 LOG_STDOUT(ERROR_UNKNOWN, "SlotTimer %u (prev %u), fired out of time %d != %d\n",
                    slot, prev_slot_slot, call SlotTimer.getNow() - prev_slot_time, (TDMA_NUM_SLOTS * SLOT_PERIOD_MS) + DISSEM_PERIOD_MS);
            }
        }
        prev_slot_time = call SlotTimer.getNow();
        prev_slot_slot = slot;
#endif

        signal TDMA.slot_started();

        call PostSlotTimer.startOneShotAt(now, SLOT_PERIOD_MS);
    }

    event void PostSlotTimer.fired()
    {
        uint32_t now, local_now, global_now;
        uint16_t s;
        int32_t timesync_overflow;

        assert(slot != BOT);

        local_now = global_now = call PostSlotTimer.gett0() + call PostSlotTimer.getdt();
        if(call GlobalTime.local2Global(&global_now) == FAIL) {
            global_now = local_now;
        }

        s = slot;

        //XXX: Potentially 'now' could negatively wrap-around
        now = local_now - (global_now - local_now + timesync_offset);
        timesync_offset = local_now - global_now;

#ifdef TOSSIM
        assert(now == local_now);
#endif

        //If timesync_offset is too large for the timer, reduce the offset for
        //this step and catch up in another timer
        if((timesync_overflow = local_now - (now + ((TDMA_NUM_SLOTS - s) * SLOT_PERIOD_MS))) > 0) {
            timesync_offset -= timesync_overflow;
        }

#ifdef TOSSIM
        assert(timesync_offset == 0);
#endif

        signal TDMA.slot_finished();
        slot_active = FALSE;
#if TDMA_TIMESYNC && TIMESYNC_PERIOD_MS > 0
        call TimesyncTimer.startOneShotAt(now, (TDMA_NUM_SLOTS - s) * SLOT_PERIOD_MS);
#else
        call DissemTimer.startOneShotAt(now, (TDMA_NUM_SLOTS - s) * SLOT_PERIOD_MS);
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

    event void TimeSyncNotify.msg_sent(error_t err) {
        return;
    }

    event void TimeSyncNotify.msg_received(error_t err) {
#if TDMA_TIMESYNC && TIMESYNC_PERIOD_MS > 0
        if(!timesync_sent) {
            timesync_sent = TRUE;
            call TimeSyncMode.send();
        }
#endif
    }
}
