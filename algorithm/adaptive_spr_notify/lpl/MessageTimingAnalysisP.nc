
//#include <scale.h>

generic module MessageTimingAnalysisP()
{
    provides interface MessageTimingAnalysis;
    provides interface Init;

    uses interface Timer<TMilli> as DetectTimer;

    uses interface Timer<TMilli> as OnTimer;
    uses interface Timer<TMilli> as OffTimer;

    uses interface MetricLogging;
    uses interface LocalTime<TMilli>;
}
implementation
{
    void startOnTimer();
    void startOffTimer();
    void startOffTimerFromMessage();

    uint32_t expected_interval_ms;
    uint32_t previous_group_time_ms;

    uint32_t average_us;
    uint32_t seen;

    uint32_t max_group_ms;

    uint32_t early_wakeup_duration_ms;

    bool message_received;
    uint32_t missed_messages;

    command error_t Init.init()
    {
        expected_interval_ms = UINT32_MAX;
        previous_group_time_ms = UINT32_MAX; // Last time a new group was started

        seen = 0;

        // Set a minimum group wait time here
        max_group_ms = 25;
        early_wakeup_duration_ms = 75;

        message_received = FALSE;
        missed_messages = 0;

        return SUCCESS;
    }

    event void DetectTimer.fired()
    {
        if (message_received)
        {
            missed_messages = 0;
        }
        else
        {
            missed_messages += 1;
        }

        if (!message_received)
        {
            const uint32_t max_value = (expected_interval_ms != UINT32_MAX)
                ? expected_interval_ms/2
                : 300;

            early_wakeup_duration_ms = min(early_wakeup_duration_ms + 5, max_value);
        }
        else
        {
            //early_wakeup_duration_ms = max(early_wakeup_duration_ms - 5, 75);
        }

        message_received = FALSE;
    }

    void update(uint32_t timestamp_ms)
    {
        const uint32_t timestamp_us = timestamp_ms * 1000;
        const uint32_t old_average = average_us;

        // It is possible that we have missed messages since the last time
        // we received a message. This means that timestamp_ms will roughly
        // be expected_interval_ms * x, where x is the number of missed messages.

        if (seen == 0)
        {
            seen += 1;
            average_us = timestamp_us;
        }
        else
        {
            seen += 1;

            if (timestamp_us >= average_us)
            {
                average_us += (timestamp_us - average_us) / seen;
            }
            else
            {
                average_us -= (average_us - timestamp_us) / seen;
            }
        }

        simdbg("stdout", "New average %" PRIu32 " old %" PRIu32 " n %" PRIu32 " value %" PRIu32,
            average_us, old_average, seen, timestamp_us);
    }

    command void MessageTimingAnalysis.expected_interval(uint32_t interval_ms)
    {
        expected_interval_ms = interval_ms;

        call DetectTimer.startPeriodic(expected_interval_ms);

        update(expected_interval_ms);
    }

    command void MessageTimingAnalysis.received(uint32_t timestamp_ms, bool is_new)
    {
        // Difference between this message and the last group message
        const uint32_t group_diff = (previous_group_time_ms != UINT32_MAX && previous_group_time_ms <= timestamp_ms)
            ? (timestamp_ms - previous_group_time_ms)
            : UINT32_MAX;

        message_received = TRUE;

        LOG_STDOUT(0, TOS_NODE_ID_SPEC ": received at=%" PRIu32 " expected=%" PRIu32 " gd=%" PRIu32 "\n",
            TOS_NODE_ID, timestamp_ms, expected_interval_ms, group_diff);

        if (is_new)
        {
            previous_group_time_ms = timestamp_ms;

            if (group_diff != UINT32_MAX)
            {
                update(group_diff / (missed_messages + 1));
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
            startOffTimerFromMessage();
        }
    }

    // At what time did the previous group start?
    command uint32_t MessageTimingAnalysis.last_group_start()
    {
       return previous_group_time_ms; 
    }

    // How long to wait between one group and the next
    // This is the time between the first new messages
    command uint32_t MessageTimingAnalysis.next_group_wait()
    {
        if (seen == 0)
        {
            return expected_interval_ms;
        }
        else
        {
            return average_us / 1000; // expected_interval_ms;//
        }
    }

    // How long to wakeup before the group starts
    command uint32_t MessageTimingAnalysis.early_wakeup_duration()
    {
        return early_wakeup_duration_ms;
    }

    // Stay away listening for the rest of the grouped messages
    command uint32_t MessageTimingAnalysis.awake_duration()
    {
        return max_group_ms;
    }

    event void OnTimer.fired()
    {
        startOffTimer();

        signal MessageTimingAnalysis.on_timer_fired();
    }

    event void OffTimer.fired()
    {    
        startOnTimer();

        signal MessageTimingAnalysis.off_timer_fired();
    }

    void startOnTimer()
    {
        if (!call OnTimer.isRunning())
        {
            const uint32_t next_group_wait = call MessageTimingAnalysis.next_group_wait();
            const uint32_t early_wakeup_duration = call MessageTimingAnalysis.early_wakeup_duration();
            const uint32_t awake_duration = call MessageTimingAnalysis.awake_duration();

            const uint32_t start = (next_group_wait == UINT32_MAX)
                ? 1
                : next_group_wait - early_wakeup_duration - awake_duration;

            simdbg("stdout", "Starting on timer in %" PRIu32 "\n", start);
            call OnTimer.startOneShot(start);
        }
    }

    // OnTimer has just fired, start off timer
    void startOffTimer()
    {
        if (!call OffTimer.isRunning())
        {
            if (call MessageTimingAnalysis.next_group_wait() != UINT32_MAX)
            {
                const uint32_t early_wakeup_duration = call MessageTimingAnalysis.early_wakeup_duration();
                const uint32_t awake_duration = call MessageTimingAnalysis.awake_duration();

                const uint32_t start = early_wakeup_duration + awake_duration;

                simdbg("stdout", "Starting off timer 2 in %" PRIu32 "\n", start);
                call OffTimer.startOneShot(start);
            }
        }
    }

    // Just received a message, consider when to turn off
    void startOffTimerFromMessage()
    {
        const uint32_t now = call LocalTime.get();

        if (!call OffTimer.isRunning())
        {
            const uint32_t last_group_start = call MessageTimingAnalysis.last_group_start(); // This is the current group
            const uint32_t awake_duration = call MessageTimingAnalysis.awake_duration();

            const uint32_t start = awake_duration - (now - last_group_start);

            simdbg("stdout", "Starting off timer 1 in %" PRIu32 " (%" PRIu32 ",%" PRIu32 ",%" PRIu32 ")\n",
                start, awake_duration, now, last_group_start);
            call OffTimer.startOneShot(start);
        }
    }

    command bool MessageTimingAnalysis.can_turn_off()
    {
        return call OnTimer.isRunning() && !call OffTimer.isRunning();
    }
}
