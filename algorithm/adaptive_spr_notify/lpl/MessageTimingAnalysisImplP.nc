
#include "average.h"

#include "SLPDutyCycleFlags.h"

generic module MessageTimingAnalysisImplP()
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

    command void MessageTimingAnalysis.expected(uint32_t duration_ms, uint32_t period_ms, uint8_t source_type)
    {
        //assert(source_type == SourceNode);

        expected_interval_ms = period_ms;

        call DetectTimer.startPeriodic(expected_interval_ms);

        incremental_average(&average_us, &seen, expected_interval_ms * 1000);
    }

    command void MessageTimingAnalysis.received(uint32_t timestamp_ms, uint8_t flags, uint8_t source_type)
    {
        const bool is_new = (flags & SLP_DUTY_CYCLE_IS_NEW) != 0;
        
        // Difference between this message and the last group message
        const uint32_t group_diff = (previous_group_time_ms != UINT32_MAX && previous_group_time_ms <= timestamp_ms)
            ? (timestamp_ms - previous_group_time_ms)
            : UINT32_MAX;

        message_received = TRUE;

        //LOG_STDOUT(0, TOS_NODE_ID_SPEC ": received at=%" PRIu32 " expected=%" PRIu32 " gd=%" PRIu32 "\n",
        //    TOS_NODE_ID, timestamp_ms, expected_interval_ms, group_diff);

        if (is_new)
        {
            previous_group_time_ms = timestamp_ms;

            if (group_diff != UINT32_MAX)
            {
                incremental_average(&average_us, &seen, (group_diff / (missed_messages + 1)) * 1000);
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

    // How long to wait between one group and the next
    // This is the time between the first new messages
    uint32_t next_group_wait(void)
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

    event void OnTimer.fired()
    {
        startOffTimer();

        signal MessageTimingAnalysis.start_radio();
    }

    event void OffTimer.fired()
    {    
        startOnTimer();

        signal MessageTimingAnalysis.stop_radio();
    }

    void startOnTimer()
    {
        if (!call OnTimer.isRunning())
        {
            const uint32_t next_group_wait_ms = next_group_wait();
            const uint32_t awake_duration = max_group_ms;

            const uint32_t start = (next_group_wait_ms == UINT32_MAX)
                ? 1
                : next_group_wait_ms - early_wakeup_duration_ms - awake_duration;

            //simdbg("stdout", "Starting on timer in %" PRIu32 "\n", start);
            call OnTimer.startOneShot(start);
        }
    }

    // OnTimer has just fired, start off timer
    void startOffTimer()
    {
        if (!call OffTimer.isRunning())
        {
            if (next_group_wait() != UINT32_MAX)
            {
                const uint32_t awake_duration = max_group_ms;

                const uint32_t start = early_wakeup_duration_ms + awake_duration;

                //simdbg("stdout", "Starting off timer 2 in %" PRIu32 "\n", start);
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
            const uint32_t last_group_start = previous_group_time_ms; // This is the current group
            const uint32_t awake_duration = max_group_ms;

            const uint32_t start = awake_duration - (now - last_group_start);

            //simdbg("stdout", "Starting off timer 1 in %" PRIu32 " (%" PRIu32 ",%" PRIu32 ",%" PRIu32 ")\n",
            //    start, awake_duration, now, last_group_start);
            call OffTimer.startOneShot(start);
        }
    }

    command bool MessageTimingAnalysis.can_turn_off()
    {
        return call OnTimer.isRunning() && !call OffTimer.isRunning();
    }
}
