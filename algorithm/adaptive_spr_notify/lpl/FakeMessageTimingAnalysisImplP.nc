
#include "../Constants.h"
#include "../FakeMessage.h"

#include "average.h"

#include "SLPDutyCycleFlags.h"

static const uint32_t choose_on_time = 50;

generic module FakeMessageTimingAnalysisImplP()
{
    provides interface MessageTimingAnalysis;
    provides interface Init;

    uses interface Timer<TMilli> as ChooseOnTimer;
    uses interface Timer<TMilli> as ChooseOffTimer;

    uses interface Timer<TMilli> as DurationOnTimer;
    uses interface Timer<TMilli> as DurationOffTimer;

    uses interface Timer<TMilli> as TempOnTimer;
    uses interface Timer<TMilli> as TempOffTimer;

    uses interface Timer<TMilli> as PermOnTimer;
    uses interface Timer<TMilli> as PermOffTimer;
    //uses interface Timer<TMilli> as PermDetectTimer;

    uses interface MetricLogging;
}
implementation
{
    void startTempOnTimer(uint32_t now);
    void startTempOffTimer(uint32_t now);
    void startTempOffTimerFromMessage(uint32_t now);

    void startPermOnTimer(uint32_t now);
    void startPermOffTimer(uint32_t now);
    void startPermOffTimerFromMessage(uint32_t now);

    uint32_t perm_expected_interval_ms;
    //uint32_t perm_average_us;
    //uint32_t perm_seen;
    //uint32_t perm_previous_group_time_ms;

    //bool perm_message_received;
    //uint32_t perm_missed_messages;


    //uint32_t temp_previous_first_duration_time_ms;
    //uint32_t temp_expected_duration_us;
    //uint32_t temp_expected_duration_seen;
    uint32_t temp_expected_duration_ms;
    uint32_t temp_expected_period_ms;

    bool temp_disabled;
    uint8_t temp_no_receive_count;

    //uint32_t temp_previous_group_time_ms;
    
    //bool temp_message_received;

    uint32_t late_wakeup_ms;
    uint32_t early_wakeup_ms;

    // How long to wait between one group and the next
    // This is the time between the first new messages
    uint32_t temp_next_duration_wait(void)
    {
        return temp_expected_duration_ms;
        //return (temp_expected_duration_us == UINT32_MAX) ? UINT32_MAX : temp_expected_duration_us / 1000;
    }
    uint32_t temp_next_period_wait(void)
    {
        return temp_expected_period_ms;
    }
    uint32_t temp_delay_wait(void)
    {
        return (temp_expected_period_ms == UINT32_MAX) ? UINT32_MAX : temp_expected_period_ms / 4;
    }
    uint32_t perm_next_period_wait(void)
    {
        return /*(perm_seen == 0) ?*/ perm_expected_interval_ms /*: perm_average_us / 1000*/;
    }

    command error_t Init.init()
    {
        //temp_expected_duration_us = UINT32_MAX;
        //temp_expected_duration_seen = 0;

        temp_expected_duration_ms = UINT32_MAX;
        temp_expected_period_ms = UINT32_MAX;

        temp_disabled = FALSE;
        temp_no_receive_count = 0;

        //temp_previous_first_duration_time_ms = UINT32_MAX; // Last time a new group was started
        //temp_previous_group_time_ms = UINT32_MAX;

        //temp_message_received = FALSE;


        perm_expected_interval_ms = UINT32_MAX;
        //perm_seen = 0;
        //perm_previous_group_time_ms = UINT32_MAX; // Last time a new group was started

        //perm_message_received = FALSE;
        //perm_missed_messages = 0;


        // Set a minimum group wait time here
        late_wakeup_ms = 150;//250
        early_wakeup_ms = 100;//150

        return SUCCESS;
    }

    /*event void PermDetectTimer.fired()
    {
        if (perm_message_received)
        {
            perm_missed_messages = 0;
        }
        else
        {
            perm_missed_messages += 1;
        }

        perm_message_received = FALSE;
    }*/

    command void MessageTimingAnalysis.expected(uint32_t duration_ms, uint32_t period_ms, uint8_t source_type, uint32_t rcvd_timestamp)
    {
        if (source_type == PermFakeNode)
        {
            //assert(duration_ms == UINT32_MAX);

            //call PermDetectTimer.startPeriodicAt(rcvd_timestamp, period_ms);

            // A PFS has changed its interval
            //if (perm_expected_interval_ms != period_ms)
            //{
            //    perm_seen = 0;
            //}

            perm_expected_interval_ms = period_ms;

            //incremental_average(&perm_average_us, &perm_seen, perm_expected_interval_ms * 1000);
        }
        else if (source_type == TempFakeNode || source_type == TailFakeNode)
        {
            //temp_expected_duration_seen = 0;
            //incremental_average(&temp_expected_duration_us, &temp_expected_duration_seen, duration_ms * 1000);

            temp_expected_duration_ms = duration_ms;
            temp_expected_period_ms = period_ms;
        }
        else
        {
            __builtin_unreachable();
        }
    }

    void received_temp_or_tail(const FakeMessage* mdata, uint32_t timestamp_ms, uint8_t flags)
    {
        const bool is_new = (flags & SLP_DUTY_CYCLE_IS_NEW) != 0;
        //const bool is_first_fake = (flags & SLP_DUTY_CYCLE_IS_FIRST_FAKE) != 0;
        const bool is_adjacent = (flags & SLP_DUTY_CYCLE_IS_ADJACENT_TO_FAKE) != 0;

        // Difference between this message and the last group message
        //const uint32_t group_diff = (temp_previous_group_time_ms != UINT32_MAX && temp_previous_group_time_ms <= timestamp_ms)
        //    ? (timestamp_ms - temp_previous_group_time_ms)
        //    : UINT32_MAX;

        //const uint32_t first_duration_diff = (temp_previous_first_duration_time_ms != UINT32_MAX && temp_previous_first_duration_time_ms <= timestamp_ms)
        //    ? (timestamp_ms - temp_previous_first_duration_time_ms)
        //    : UINT32_MAX;

        //temp_message_received = TRUE;

        //LOG_STDOUT(0, "received FAKE at=%" PRIu32 " from=%" PRIu16 " count=%" PRIu16 " new=%" PRIu8 " first=%" PRIu8 " ajd=%" PRIu8 "\n",
        //    timestamp_ms, mdata->source_id, mdata->ultimate_sender_fake_count, is_new, is_first_fake, is_adjacent);

        /*if (call TempOffTimer.isRunning())
        {
            const uint32_t radio_off_at = call TempOffTimer.gett0() + call TempOffTimer.getdt();
            const uint32_t radio_on_at = radio_off_at - early_wakeup_ms - late_wakeup_ms;

            const int32_t a = timestamp_ms - radio_on_at;
            const uint32_t b = radio_off_at - timestamp_ms;

            LOG_STDOUT(0, "Received TempFake %" PRIi32 " %" PRIu32 " %" PRIu32 " w=%" PRIi32 "\n",
                a, timestamp_ms, b, a + b);
        }*/

        if (is_new)
        {
            /*temp_previous_group_time_ms = timestamp_ms;

            if (is_first_fake)
            {
                temp_previous_first_duration_time_ms = timestamp_ms;

                /*if (first_duration_diff != UINT32_MAX)
                {
                    //incremental_average(&temp_expected_duration_us, &temp_expected_duration_seen,
                    //    (first_duration_diff / (temp_missed_messages + 1)) * 1000);
                }* /
            }*/

            startTempOffTimerFromMessage(timestamp_ms);

            {
                // When receiving the nth fake message we need to subtract this from the time to wait
                // ultimate_sender_fake_count starts at 0 for the first message
                const uint8_t nth_message_delay = mdata->ultimate_sender_fake_count * temp_expected_period_ms;

                // Wake up for the first fake message from the next fake node
                if (!call DurationOnTimer.isRunning())
                {
                    const uint32_t temp_duration_ms = temp_next_duration_wait();

                    call DurationOnTimer.startOneShotAt(timestamp_ms,
                        temp_duration_ms - nth_message_delay - early_wakeup_ms);
                }

                // Check if we should wake up for choose messages
                if (is_adjacent && !call ChooseOnTimer.isRunning())
                {
                    const uint32_t temp_duration_ms = temp_next_duration_wait();
                    const uint32_t temp_delay_ms = temp_delay_wait();

                    const uint32_t choose_start =
                            temp_duration_ms - temp_delay_ms - nth_message_delay - early_wakeup_ms;

                    //assert(temp_duration_ms != UINT32_MAX && temp_delay_ms != UINT32_MAX);

                    call ChooseOnTimer.startOneShotAt(timestamp_ms, choose_start);
                }
            }
        }
        /*else
        {
            if (group_diff != UINT32_MAX)
            {
                late_wakeup_ms = max(late_wakeup_ms, group_diff);
            }
        }*/
    }

    void received_perm(const FakeMessage* mdata, uint32_t timestamp_ms, uint8_t flags)
    {
        const bool is_new = (flags & SLP_DUTY_CYCLE_IS_NEW) != 0;

        // Difference between this message and the last group message
        //const uint32_t group_diff = (perm_previous_group_time_ms != UINT32_MAX && perm_previous_group_time_ms <= timestamp_ms)
        //    ? (timestamp_ms - perm_previous_group_time_ms)
        //    : UINT32_MAX;

        //perm_message_received = TRUE;

        //LOG_STDOUT(0, TOS_NODE_ID_SPEC ": received at=%" PRIu32 " expected=%" PRIu32 " gd=%" PRIu32 "\n",
        //    TOS_NODE_ID, timestamp_ms, temp_expected_interval_ms, group_diff);

        
        if (is_new)
        {
            //perm_previous_group_time_ms = timestamp_ms;

            /*if (group_diff != UINT32_MAX)
            {
                incremental_average(&perm_average_us, &perm_seen, (group_diff * 1000) / (perm_missed_messages + 1));
            }*/

            startPermOffTimerFromMessage(timestamp_ms);
        }
        /*else
        {
            if (group_diff != UINT32_MAX)
            {
                late_wakeup_ms = max(late_wakeup_ms, group_diff);
            }
        }*/
    }

    command void MessageTimingAnalysis.received(message_t* msg, const void* data, uint32_t timestamp_ms, uint8_t flags, uint8_t source_type)
    {
        const FakeMessage* mdata = (const FakeMessage*)data;

        if (source_type == TempFakeNode || source_type == TailFakeNode)
        {
            received_temp_or_tail(mdata, timestamp_ms, flags);
        }
        else if (source_type == PermFakeNode)
        {
            received_perm(mdata, timestamp_ms, flags);
        }
        else
        {
            __builtin_unreachable();
        }

        if (!temp_disabled)
        {
            if (call TempOffTimer.isRunning() && !call TempOnTimer.isRunning())
            {
                temp_no_receive_count = 0;
            }
            else
            {
                temp_no_receive_count += 1;
            }
    
            if (perm_expected_interval_ms != UINT32_MAX && temp_no_receive_count >= 3)
            {
                temp_disabled = TRUE;
                call TempOffTimer.stop();
                call TempOnTimer.stop();
            }
        }
    }

    event void ChooseOnTimer.fired()
    {
        const uint32_t now = call ChooseOnTimer.gett0() + call ChooseOnTimer.getdt();

#ifdef SLP_USES_GUI_OUPUT
        METRIC_GENERIC(METRIC_GENERIC_DUTY_CYCLE_ON_CHOOSE, "");
#endif
        signal MessageTimingAnalysis.start_radio();

        call ChooseOffTimer.startOneShotAt(now, choose_on_time);
    }

    event void ChooseOffTimer.fired()
    {
        signal MessageTimingAnalysis.stop_radio();
    }

    event void DurationOnTimer.fired()
    {
        const uint32_t now = call DurationOnTimer.gett0() + call DurationOnTimer.getdt();

#ifdef SLP_USES_GUI_OUPUT
        METRIC_GENERIC(METRIC_GENERIC_DUTY_CYCLE_ON_FAKE, "");
#endif
        signal MessageTimingAnalysis.start_radio();

        call DurationOffTimer.startOneShotAt(now, early_wakeup_ms + late_wakeup_ms);
    }

    event void DurationOffTimer.fired()
    {
        const uint32_t now = call DurationOffTimer.gett0() + call DurationOffTimer.getdt();

        signal MessageTimingAnalysis.stop_radio();

        // Stop on on timer as we are about to reset it
        call TempOnTimer.stop();

        startTempOnTimer(now);
    }

    event void TempOnTimer.fired()
    {
        const uint32_t now = call TempOnTimer.gett0() + call TempOnTimer.getdt();

#ifdef SLP_USES_GUI_OUPUT
        METRIC_GENERIC(METRIC_GENERIC_DUTY_CYCLE_ON_FAKE, "");
#endif
        signal MessageTimingAnalysis.start_radio();

        startTempOffTimer(now);
    }

    event void TempOffTimer.fired()
    {    
        const uint32_t now = call TempOffTimer.gett0() + call TempOffTimer.getdt();

        signal MessageTimingAnalysis.stop_radio();

        startTempOnTimer(now);
    }

    void startTempOnTimer(uint32_t now)
    {
        if (!call TempOnTimer.isRunning())
        {
            const uint32_t next_wait_ms = temp_next_period_wait();

            if (next_wait_ms == UINT32_MAX)
            {
                ERROR_OCCURRED(ErrorUnknownTempPeriodWait, "Restarting radio immediately. temp_next_period_wait unknown.\n");

                signal MessageTimingAnalysis.start_radio();
            }
            else
            {
                const uint32_t start = next_wait_ms - early_wakeup_ms - late_wakeup_ms;

                //simdbg("stdout", "Starting on timer in %" PRIu32 "\n", start);

                call TempOnTimer.startOneShotAt(now, start);
            }
        }
    }

    // OnTimer has just fired, start off timer
    void startTempOffTimer(uint32_t now)
    {
        if (!call TempOffTimer.isRunning())
        {
            const uint32_t start = early_wakeup_ms + late_wakeup_ms;

            call TempOffTimer.startOneShotAt(now, start);
        }
    }

    // Just received a message, consider when to turn off
    void startTempOffTimerFromMessage(uint32_t now)
    {
        if (!call TempOffTimer.isRunning())
        {
            call TempOffTimer.startOneShotAt(now, late_wakeup_ms);
        }
    }

    event void PermOnTimer.fired()
    {
        const uint32_t now = call PermOnTimer.gett0() + call PermOnTimer.getdt();

#ifdef SLP_USES_GUI_OUPUT
        METRIC_GENERIC(METRIC_GENERIC_DUTY_CYCLE_ON_FAKE, "");
#endif
        signal MessageTimingAnalysis.start_radio();

        startPermOffTimer(now);
    }

    event void PermOffTimer.fired()
    {
        const uint32_t now = call PermOffTimer.gett0() + call PermOffTimer.getdt();

        signal MessageTimingAnalysis.stop_radio();

        startPermOnTimer(now);
    }

    void startPermOnTimer(uint32_t now)
    {
        if (!call PermOnTimer.isRunning())
        {
            const uint32_t next_wait_ms = perm_next_period_wait();

            if (next_wait_ms == UINT32_MAX)
            {
                ERROR_OCCURRED(ErrorUnknownPermPeriodWait, "Restarting radio immediately. perm_next_period_wait unknown.\n");

                signal MessageTimingAnalysis.start_radio();
            }
            else
            {
                const uint32_t start = next_wait_ms - early_wakeup_ms - late_wakeup_ms;

                call PermOnTimer.startOneShotAt(now, start);
            }
        }
    }

    // OnTimer has just fired, start off timer
    void startPermOffTimer(uint32_t now)
    {
        if (!call PermOffTimer.isRunning())
        {
            const uint32_t start = early_wakeup_ms + late_wakeup_ms;

            call PermOffTimer.startOneShotAt(now, start);
        }
    }

    // Just received a message, consider when to turn off
    void startPermOffTimerFromMessage(uint32_t now)
    {
        if (!call PermOffTimer.isRunning())
        {
            call PermOffTimer.startOneShotAt(now, late_wakeup_ms);
        }
    }

    command bool MessageTimingAnalysis.can_turn_off()
    {
        return
            // Can turn off if not listening for a fake from a TempFS or TailFS
            (temp_disabled || (call TempOnTimer.isRunning() && !call TempOffTimer.isRunning())) &&

            // And, we either haven't started PFS duty cycling, or we are in the PFS off period
            /*((!call PermOnTimer.isRunning() && !call PermOffTimer.isRunning()) ||
             (call PermOnTimer.isRunning() && !call PermOffTimer.isRunning()))*/
            !call PermOffTimer.isRunning() &&

            !call ChooseOffTimer.isRunning()
            ;
    }
}
