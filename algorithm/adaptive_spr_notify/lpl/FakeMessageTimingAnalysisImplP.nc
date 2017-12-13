
#include "../Constants.h"
#include "../FakeMessage.h"

#include "average.h"

#include "SLPDutyCycleFlags.h"

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
    uses interface Timer<TMilli> as PermDetectTimer;

    uses interface MetricLogging;
    uses interface LocalTime<TMilli>;
}
implementation
{
    void startTempOnTimer(uint32_t now);
    void startTempOffTimer(uint32_t now);
    void startTempOffTimerFromMessage();

    void startPermOnTimer(uint32_t now);
    void startPermOffTimer(uint32_t now);
    void startPermOffTimerFromMessage();

    uint32_t perm_expected_interval_ms;
    //uint32_t perm_average_us;
    //uint32_t perm_seen;
    uint32_t perm_previous_group_time_ms;

    //bool perm_message_received;
    //uint32_t perm_missed_messages;


    uint32_t temp_previous_first_duration_time_ms;
    //uint32_t temp_expected_duration_us;
    //uint32_t temp_expected_duration_seen;
    uint32_t temp_expected_duration_ms;
    uint32_t temp_expected_period_ms;

    uint32_t temp_previous_group_time_ms;
    
    //bool temp_message_received;

    uint32_t max_wakeup_time_ms;
    uint32_t early_wakeup_duration_ms;

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

        temp_previous_first_duration_time_ms = UINT32_MAX; // Last time a new group was started
        temp_previous_group_time_ms = UINT32_MAX;

        //temp_message_received = FALSE;


        perm_expected_interval_ms = UINT32_MAX;
        //perm_seen = 0;
        //perm_previous_group_time_ms = UINT32_MAX; // Last time a new group was started

        //perm_message_received = FALSE;
        //perm_missed_messages = 0;


        // Set a minimum group wait time here
        max_wakeup_time_ms = 50;
        early_wakeup_duration_ms = 75;

        return SUCCESS;
    }

    event void PermDetectTimer.fired()
    {
        /*if (perm_message_received)
        {
            perm_missed_messages = 0;
        }
        else
        {
            perm_missed_messages += 1;
        }

        perm_message_received = FALSE;*/
    }

    command void MessageTimingAnalysis.expected(uint32_t duration_ms, uint32_t period_ms, uint8_t source_type, uint32_t rcvd_timestamp)
    {
        if (source_type == PermFakeNode)
        {
            call PermDetectTimer.startPeriodicAt(rcvd_timestamp, period_ms);

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
        const bool is_first_fake = (flags & SLP_DUTY_CYCLE_IS_FIRST_FAKE) != 0;
        const bool is_adjacent = (flags & SLP_DUTY_CYCLE_IS_ADJACENT_TO_FAKE) != 0;

        // Difference between this message and the last group message
        const uint32_t group_diff = (temp_previous_group_time_ms != UINT32_MAX && temp_previous_group_time_ms <= timestamp_ms)
            ? (timestamp_ms - temp_previous_group_time_ms)
            : UINT32_MAX;

        //const uint32_t first_duration_diff = (temp_previous_first_duration_time_ms != UINT32_MAX && temp_previous_first_duration_time_ms <= timestamp_ms)
        //    ? (timestamp_ms - temp_previous_first_duration_time_ms)
        //    : UINT32_MAX;

        //temp_message_received = TRUE;

        //LOG_STDOUT(0, TOS_NODE_ID_SPEC ": received at=%" PRIu32 " expected=%" PRIu32 " gd=%" PRIu32 "\n",
        //    TOS_NODE_ID, timestamp_ms, temp_expected_interval_ms, group_diff);

        if (is_new)
        {
            temp_previous_group_time_ms = timestamp_ms;

            if (is_first_fake)
            {
                temp_previous_first_duration_time_ms = timestamp_ms;

                /*if (first_duration_diff != UINT32_MAX)
                {
                    //incremental_average(&temp_expected_duration_us, &temp_expected_duration_seen,
                    //    (first_duration_diff / (temp_missed_messages + 1)) * 1000);
                }*/
            }

            startTempOffTimerFromMessage();

            if (is_first_fake)
            {
                // Wake up for the first fake message from the next fake node
                if (!call DurationOnTimer.isRunning())
                {
                    call DurationOnTimer.startOneShotAt(timestamp_ms, temp_next_duration_wait() - early_wakeup_duration_ms);
                }

                // Check if we should wake up for choose messages
                if (is_adjacent && !call ChooseOnTimer.isRunning())
                {
                    const uint32_t temp_duration_ms = temp_next_duration_wait();
                    const uint32_t temp_delay_ms = temp_delay_wait();

                    if (temp_duration_ms != UINT32_MAX && temp_delay_ms != UINT32_MAX)
                    {
                        // TODO: consider receiving the nth fake message
                        //const uint8_t nth_message_delay = (mdata->ultimate_sender_fake_count - 1) * temp_expected_period_ms;

                        const uint32_t choose_start =
                            temp_duration_ms - temp_delay_ms /*- nth_message_delay*/ - early_wakeup_duration_ms;

                        call ChooseOnTimer.startOneShotAt(timestamp_ms, choose_start);
                    }
                }
            }
        }
        else
        {
            if (group_diff != UINT32_MAX)
            {
                max_wakeup_time_ms = max(max_wakeup_time_ms, group_diff);
            }
        }
    }

    void received_perm(const FakeMessage* mdata, uint32_t timestamp_ms, uint8_t flags)
    {
        const bool is_new = (flags & SLP_DUTY_CYCLE_IS_NEW) != 0;

        // Difference between this message and the last group message
        const uint32_t group_diff = (perm_previous_group_time_ms != UINT32_MAX && perm_previous_group_time_ms <= timestamp_ms)
            ? (timestamp_ms - perm_previous_group_time_ms)
            : UINT32_MAX;

        //perm_message_received = TRUE;

        //LOG_STDOUT(0, TOS_NODE_ID_SPEC ": received at=%" PRIu32 " expected=%" PRIu32 " gd=%" PRIu32 "\n",
        //    TOS_NODE_ID, timestamp_ms, temp_expected_interval_ms, group_diff);

        if (is_new)
        {
            perm_previous_group_time_ms = timestamp_ms;

            /*if (group_diff != UINT32_MAX)
            {
                incremental_average(&perm_average_us, &perm_seen, (group_diff * 1000) / (perm_missed_messages + 1));
            }*/

            startPermOffTimerFromMessage();
        }
        else
        {
            if (group_diff != UINT32_MAX)
            {
                max_wakeup_time_ms = max(max_wakeup_time_ms, group_diff);
            }
        }
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
    }

    event void TempOnTimer.fired()
    {
        const uint32_t now = call TempOnTimer.getNow();

        signal MessageTimingAnalysis.start_radio();

        startTempOffTimer(now);
    }

    event void TempOffTimer.fired()
    {    
        const uint32_t now = call TempOffTimer.getNow();

        signal MessageTimingAnalysis.stop_radio();

        startTempOnTimer(now);
    }

    event void ChooseOnTimer.fired()
    {
        const uint32_t now = call ChooseOnTimer.getNow();

        signal MessageTimingAnalysis.start_radio();

        call ChooseOffTimer.startOneShotAt(now, early_wakeup_duration_ms + max_wakeup_time_ms);
    }

    event void ChooseOffTimer.fired()
    {
        signal MessageTimingAnalysis.stop_radio();
    }

    event void DurationOnTimer.fired()
    {
        const uint32_t now = call DurationOnTimer.getNow();

        signal MessageTimingAnalysis.start_radio();

        call DurationOffTimer.startOneShotAt(now, early_wakeup_duration_ms + max_wakeup_time_ms);
    }

    event void DurationOffTimer.fired()
    {
        const uint32_t now = call DurationOffTimer.getNow();

        signal MessageTimingAnalysis.stop_radio();

        // If we didn't receive a message, then start the on timer
        startTempOnTimer(now);
    }

    void startTempOnTimer(uint32_t now)
    {
        if (!call TempOnTimer.isRunning())
        {
            const uint32_t next_wait_ms = temp_next_period_wait();

            if (next_wait_ms == UINT32_MAX)
            {
                signal MessageTimingAnalysis.start_radio();
            }
            else
            {
                const uint32_t start = next_wait_ms - early_wakeup_duration_ms - max_wakeup_time_ms;

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
            if (temp_next_period_wait() != UINT32_MAX)
            {
                const uint32_t start = early_wakeup_duration_ms + max_wakeup_time_ms;

                //simdbg("stdout", "Starting off timer 2 in %" PRIu32 "\n", start);
                call TempOffTimer.startOneShotAt(now, start);
            }
        }
    }

    // Just received a message, consider when to turn off
    void startTempOffTimerFromMessage()
    {
        //if (!call TempOffTimer.isRunning())
        {
            //simdbg("stdout", "Starting off timer 1 in %" PRIu32 " (%" PRIu32 ",%" PRIu32 ",%" PRIu32 ")\n",
            //    start, awake_duration, now, temp_previous_group_time_ms);
            call TempOffTimer.startOneShotAt(temp_previous_group_time_ms, max_wakeup_time_ms);
        }
    }

    event void PermOnTimer.fired()
    {
        const uint32_t now = call PermOnTimer.getNow();

        signal MessageTimingAnalysis.start_radio();

        startPermOffTimer(now);
    }

    event void PermOffTimer.fired()
    {    
        const uint32_t now = call PermOffTimer.getNow();

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
                signal MessageTimingAnalysis.start_radio();
            }
            else
            {
                const uint32_t start = next_wait_ms - early_wakeup_duration_ms - max_wakeup_time_ms;

                //simdbg("stdout", "Starting on timer in %" PRIu32 "\n", start);

                call PermOnTimer.startOneShotAt(now, start);
            }
        }
    }

    // OnTimer has just fired, start off timer
    void startPermOffTimer(uint32_t now)
    {
        if (!call PermOffTimer.isRunning())
        {
            if (perm_next_period_wait() != UINT32_MAX)
            {
                const uint32_t start = early_wakeup_duration_ms + max_wakeup_time_ms;

                //simdbg("stdout", "Starting off timer 2 in %" PRIu32 "\n", start);
                call PermOffTimer.startOneShotAt(now, start);
            }
        }
    }

    // Just received a message, consider when to turn off
    void startPermOffTimerFromMessage()
    {
        //if (!call PermOffTimer.isRunning())
        {
            //simdbg("stdout", "Starting off timer 1 in %" PRIu32 " (%" PRIu32 ",%" PRIu32 ",%" PRIu32 ")\n",
            //    start, awake_duration, now, temp_previous_group_time_ms);
            call PermOffTimer.startOneShotAt(perm_previous_group_time_ms, max_wakeup_time_ms);
        }
    }

    command bool MessageTimingAnalysis.can_turn_off()
    {
        return
            // Can turn off if not listening for a fake from a TempFS or TailFS
            (call TempOnTimer.isRunning() && !call TempOffTimer.isRunning()) &&

            // And, we either haven't started PFS duty cycling, or we are in the PFS off period
            /*((!call PermOnTimer.isRunning() && !call PermOffTimer.isRunning()) ||
             (call PermOnTimer.isRunning() && !call PermOffTimer.isRunning()))*/
            !call PermOffTimer.isRunning() &&

            !call ChooseOffTimer.isRunning()
            ;
    }
}
