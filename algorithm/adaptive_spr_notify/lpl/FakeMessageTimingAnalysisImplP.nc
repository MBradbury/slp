
#include "../Constants.h"
#include "average.h"

generic module FakeMessageTimingAnalysisImplP()
{
    provides interface MessageTimingAnalysis;
    provides interface Init;

    uses interface Timer<TMilli> as TempDurationTimer;
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
    void startTempOnTimer();
    void startTempOffTimer();
    void startTempOffTimerFromMessage();

    void startPermOnTimer();
    void startPermOffTimer();
    void startPermOffTimerFromMessage();

    uint32_t perm_expected_interval_ms;
    uint32_t perm_average_us;
    uint32_t perm_seen;
    uint32_t perm_previous_group_time_ms;

    bool perm_message_received;
    uint32_t perm_missed_messages;


    uint32_t temp_expected_duration_ms;
    uint32_t temp_expected_period_ms;
    //uint32_t temp_average_us;
    //uint32_t temp_seen;
    uint32_t temp_previous_group_time_ms;

    bool temp_message_received;

    uint32_t max_group_ms;
    uint32_t early_wakeup_duration_ms;    

    command error_t Init.init()
    {
        temp_expected_duration_ms = UINT32_MAX;
        temp_expected_period_ms = UINT32_MAX;
        //temp_seen = 0;
        temp_previous_group_time_ms = UINT32_MAX; // Last time a new group was started

        temp_message_received = FALSE;


        perm_expected_interval_ms = UINT32_MAX;
        perm_seen = 0;
        perm_previous_group_time_ms = UINT32_MAX; // Last time a new group was started

        perm_message_received = FALSE;
        perm_missed_messages = 0;


        // Set a minimum group wait time here
        max_group_ms = 50;
        early_wakeup_duration_ms = 50;

        return SUCCESS;
    }

    event void PermDetectTimer.fired()
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
    }

    command void MessageTimingAnalysis.expected(uint32_t duration_ms, uint32_t period_ms, uint8_t source_type)
    {
        if (source_type == PermFakeNode)
        {
            call PermDetectTimer.stop();

            perm_expected_interval_ms = period_ms;

            call PermDetectTimer.startPeriodic(perm_expected_interval_ms);

            // A PFS has changed its interval
            if (perm_expected_interval_ms != period_ms)
            {
                perm_seen = 0;
            }

            incremental_average(&perm_average_us, &perm_seen, perm_expected_interval_ms * 1000);
        }
        else if (source_type == TempFakeNode || source_type == TailFakeNode)
        {
            temp_expected_duration_ms = duration_ms;
            temp_expected_period_ms = period_ms;
        }
        else
        {
            __builtin_unreachable();
        }
    }

    void received_temp_or_tail(uint32_t timestamp_ms, bool is_new)
    {
        // Difference between this message and the last group message
        const uint32_t group_diff = (temp_previous_group_time_ms != UINT32_MAX && temp_previous_group_time_ms <= timestamp_ms)
            ? (timestamp_ms - temp_previous_group_time_ms)
            : UINT32_MAX;

        temp_message_received = TRUE;

        //LOG_STDOUT(0, TOS_NODE_ID_SPEC ": received at=%" PRIu32 " expected=%" PRIu32 " gd=%" PRIu32 "\n",
        //    TOS_NODE_ID, timestamp_ms, temp_expected_interval_ms, group_diff);

        if (is_new)
        {
            temp_previous_group_time_ms = timestamp_ms;

            if (group_diff != UINT32_MAX)
            {
                //incremental_average(&temp_average_us, &temp_seen, (group_diff / (temp_missed_messages + 1)) * 1000);
            }
        }
        else
        {
            if (group_diff != UINT32_MAX)
            {
                max_group_ms = max(max_group_ms, group_diff);
            }
        }

        if (is_new)
        {
            startTempOffTimerFromMessage();
        }
    }

    void received_perm(uint32_t timestamp_ms, bool is_new)
    {
        // Difference between this message and the last group message
        const uint32_t group_diff = (perm_previous_group_time_ms != UINT32_MAX && perm_previous_group_time_ms <= timestamp_ms)
            ? (timestamp_ms - perm_previous_group_time_ms)
            : UINT32_MAX;

        perm_message_received = TRUE;

        //LOG_STDOUT(0, TOS_NODE_ID_SPEC ": received at=%" PRIu32 " expected=%" PRIu32 " gd=%" PRIu32 "\n",
        //    TOS_NODE_ID, timestamp_ms, temp_expected_interval_ms, group_diff);

        if (is_new)
        {
            perm_previous_group_time_ms = timestamp_ms;

            if (group_diff != UINT32_MAX)
            {
                incremental_average(&perm_average_us, &perm_seen, (group_diff / (perm_missed_messages + 1)) * 1000);
            }
        }
        else
        {
            if (group_diff != UINT32_MAX)
            {
                max_group_ms = max(max_group_ms, group_diff);
            }
        }

        if (is_new)
        {
            startPermOffTimerFromMessage();
        }
    }

    command void MessageTimingAnalysis.received(uint32_t timestamp_ms, bool is_new, uint8_t source_type)
    {
        if (source_type == TempFakeNode || source_type == TailFakeNode)
        {
            received_temp_or_tail(timestamp_ms, is_new);
        }
        else if (source_type == PermFakeNode)
        {
            received_perm(timestamp_ms, is_new);
        }
        else
        {
            __builtin_unreachable();
        }
    }

    // How long to wait between one group and the next
    // This is the time between the first new messages
    uint32_t temp_next_duration_wait(void)
    {
        return temp_expected_duration_ms;
    }
    uint32_t temp_next_period_wait(void)
    {
        return temp_expected_period_ms;
    }
    uint32_t temp_delay_wait(void)
    {
        return temp_expected_period_ms / 4;
    }
    uint32_t perm_next_period_wait(void)
    {
        return (perm_seen == 0) ? perm_expected_interval_ms : perm_average_us / 1000;
    }

    event void TempDurationTimer.fired()
    {
        call TempOffTimer.stop();
        call TempOnTimer.stop();

        startTempOffTimer();

        call TempDurationTimer.startOneShot(temp_next_duration_wait());

        // TODO: Only start the radio if we are expecting a choose message
        signal MessageTimingAnalysis.start_radio();
    }

    event void TempOnTimer.fired()
    {
        startTempOffTimer();

        signal MessageTimingAnalysis.start_radio();
    }

    event void TempOffTimer.fired()
    {    
        startTempOnTimer();

        signal MessageTimingAnalysis.stop_radio();
    }

    void startTempOnTimer()
    {
        if (!call TempOnTimer.isRunning())
        {
            const uint32_t next_wait_ms = (call TempDurationTimer.isRunning()) ? temp_next_period_wait() : temp_delay_wait();
            const uint32_t awake_duration = max_group_ms;

            if (next_wait_ms == UINT32_MAX)
            {
                signal MessageTimingAnalysis.start_radio();
            }
            else
            {
                const uint32_t start = next_wait_ms - early_wakeup_duration_ms - awake_duration;

                //simdbg("stdout", "Starting on timer in %" PRIu32 "\n", start);

                call TempOnTimer.startOneShot(start);
            }
        }
    }

    // OnTimer has just fired, start off timer
    void startTempOffTimer()
    {
        if (!call TempOffTimer.isRunning())
        {
            //if (temp_next_group_wait() != UINT32_MAX)
            {
                const uint32_t awake_duration = max_group_ms;

                const uint32_t start = early_wakeup_duration_ms + awake_duration;

                //simdbg("stdout", "Starting off timer 2 in %" PRIu32 "\n", start);
                call TempOffTimer.startOneShot(start);
            }
        }
    }

    // Just received a message, consider when to turn off
    void startTempOffTimerFromMessage()
    {
        const uint32_t now = call LocalTime.get();

        if (!call TempOffTimer.isRunning())
        {
            const uint32_t awake_duration = max_group_ms;

            const uint32_t start = awake_duration - (now - temp_previous_group_time_ms);

            //simdbg("stdout", "Starting off timer 1 in %" PRIu32 " (%" PRIu32 ",%" PRIu32 ",%" PRIu32 ")\n",
            //    start, awake_duration, now, temp_previous_group_time_ms);
            call TempOffTimer.startOneShot(start);
        }
    }

    event void PermOnTimer.fired()
    {
        startPermOffTimer();

        signal MessageTimingAnalysis.start_radio();
    }

    event void PermOffTimer.fired()
    {    
        startPermOnTimer();

        signal MessageTimingAnalysis.stop_radio();
    }

    void startPermOnTimer()
    {
        if (!call PermOnTimer.isRunning())
        {
            const uint32_t next_wait_ms = perm_next_period_wait();
            const uint32_t awake_duration = max_group_ms;

            if (next_wait_ms == UINT32_MAX)
            {
                signal MessageTimingAnalysis.start_radio();
            }
            else
            {
                const uint32_t start = next_wait_ms - early_wakeup_duration_ms - awake_duration;

                //simdbg("stdout", "Starting on timer in %" PRIu32 "\n", start);

                call PermOnTimer.startOneShot(start);
            }
        }
    }

    // OnTimer has just fired, start off timer
    void startPermOffTimer()
    {
        if (!call PermOffTimer.isRunning())
        {
            if (perm_next_period_wait() != UINT32_MAX)
            {
                const uint32_t awake_duration = max_group_ms;

                const uint32_t start = early_wakeup_duration_ms + awake_duration;

                //simdbg("stdout", "Starting off timer 2 in %" PRIu32 "\n", start);
                call PermOffTimer.startOneShot(start);
            }
        }
    }

    // Just received a message, consider when to turn off
    void startPermOffTimerFromMessage()
    {
        const uint32_t now = call LocalTime.get();

        if (!call PermOffTimer.isRunning())
        {
            const uint32_t awake_duration = max_group_ms;

            const uint32_t start = awake_duration - (now - perm_previous_group_time_ms);

            //simdbg("stdout", "Starting off timer 1 in %" PRIu32 " (%" PRIu32 ",%" PRIu32 ",%" PRIu32 ")\n",
            //    start, awake_duration, now, temp_previous_group_time_ms);
            call PermOffTimer.startOneShot(start);
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
            !call PermOffTimer.isRunning()
            ;
    }
}
