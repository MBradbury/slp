
#include "average.h"

#include "SLPDutyCycleFlags.h"

generic module MessageTimingAnalysisImplP()
{
    provides interface MessageTimingAnalysis;
    provides interface Init;

    //uses interface Timer<TMilli> as DetectTimer;

    uses interface Timer<TMilli> as OnTimer;
    uses interface Timer<TMilli> as OffTimer;

    uses interface MetricLogging;
}
implementation
{
    void startOnTimer(uint32_t now);
    void startOffTimer(uint32_t now);
    void startOffTimerFromMessage(uint32_t now);

    uint32_t next_group_wait(void);

    uint32_t expected_interval_ms;
    //uint32_t previous_group_time_ms;

    //uint32_t average_us;
    //uint32_t seen;

    uint32_t max_wakeup_time_ms;

    uint32_t early_wakeup_duration_ms;

    //bool message_received;
    //uint32_t missed_messages;

    command error_t Init.init()
    {
        expected_interval_ms = UINT32_MAX;
        //previous_group_time_ms = UINT32_MAX; // Last time a new group was started

        //seen = 0;

        // Set a minimum group wait time here
        max_wakeup_time_ms = 50;
        early_wakeup_duration_ms = 30;

        //message_received = FALSE;
        //missed_messages = 0;

        return SUCCESS;
    }

    /*event void DetectTimer.fired()
    {
        call DetectTimer.startOneShot(next_group_wait());

        if (message_received)
        {
            missed_messages = 0;
        }
        else
        {
            missed_messages += 1;
        }

        /*if (!message_received)
        {
            const uint32_t max_value = (expected_interval_ms != UINT32_MAX)
                ? expected_interval_ms/2
                : 300;

            early_wakeup_duration_ms = min(early_wakeup_duration_ms + 5, max_value);
        }
        else
        {
            //early_wakeup_duration_ms = max(early_wakeup_duration_ms - 5, 75);
        }* /

        message_received = FALSE;
    }*/

    command void MessageTimingAnalysis.expected(uint32_t duration_ms, uint32_t period_ms, uint8_t source_type, uint32_t rcvd_timestamp)
    {
        //assert(source_type == SourceNode);

        // TODO: Look into a way to do this that performs well
        //call DetectTimer.startOneShotAt(rcvd_timestamp, period_ms);

        if (period_ms != UINT32_MAX)
        {
            expected_interval_ms = period_ms;
        }
    }

    command void MessageTimingAnalysis.received(message_t* msg, const void* data, uint32_t timestamp_ms, uint8_t flags, uint8_t source_type)
    {
        const bool is_new = (flags & SLP_DUTY_CYCLE_IS_NEW) != 0;

        // Difference between this message and the last group message
        // Sometimes we may think that this message arrived before a previous message
        // Typically the difference is in the order of 1ms.
        //const uint32_t group_diff = (previous_group_time_ms != UINT32_MAX && previous_group_time_ms <= timestamp_ms)
        //    ? (timestamp_ms - previous_group_time_ms)
        //    : UINT32_MAX;

        //message_received = TRUE;

        //LOG_STDOUT(0, TOS_NODE_ID_SPEC ": received Normal at=%" PRIu32 " v=%" PRIu8 "\n",
        //    TOS_NODE_ID, timestamp_ms, (flags & SLP_DUTY_CYCLE_VALID_TIMESTAMP) != 1);

        /*if (call OffTimer.isRunning())
        {
            const uint32_t radio_off_at = call OffTimer.gett0() + call OffTimer.getdt();
            const uint32_t radio_on_at = radio_off_at - early_wakeup_duration_ms - max_wakeup_time_ms;

            const int32_t a = timestamp_ms - radio_on_at;
            const uint32_t b = radio_off_at - timestamp_ms;

            LOG_STDOUT(0, "Received Normal %" PRIi32 " %" PRIu32 " %" PRIu32 " w=%" PRIi32 "\n",
                a, timestamp_ms, b, a + b);
        }*/

        if (is_new)
        {
            //previous_group_time_ms = timestamp_ms;

            //if (group_diff != UINT32_MAX)
            //{
            //    incremental_average(&average_us, &seen, (group_diff * 1000) / (missed_messages + 1));
            //}

            startOffTimerFromMessage(timestamp_ms);
        }
        /*else
        {
            if (group_diff != UINT32_MAX)
            {
                max_wakeup_time_ms = max(max_wakeup_time_ms, group_diff);
            }
        }*/
    }

    // How long to wait between one group and the next
    // This is the time between the first new messages
    uint32_t next_group_wait(void)
    {
        //if (seen == 0)
        //{
            return expected_interval_ms;
        //}
        //else
        //{
        //    return average_us / 1000;
        //}
    }

    event void OnTimer.fired()
    {
        const uint32_t now = call OnTimer.gett0() + call OnTimer.getdt();

        signal MessageTimingAnalysis.start_radio();

        startOffTimer(now);
    }

    event void OffTimer.fired()
    {
        const uint32_t now = call OffTimer.gett0() + call OffTimer.getdt();

        signal MessageTimingAnalysis.stop_radio();

        startOnTimer(now);
    }

    void startOnTimer(uint32_t now)
    {
        if (!call OnTimer.isRunning())
        {
            const uint32_t next_group_wait_ms = next_group_wait();

            // Don't know how long to wait for, so just start the radio
            if (next_group_wait_ms == UINT32_MAX)
            {
                ERROR_OCCURRED(ErrorUnknownNormalPeriodWait, "Restarting radio immediately. next_group_wait unknown.\n");

                signal MessageTimingAnalysis.start_radio();
            }
            else
            {
                const uint32_t start = next_group_wait_ms - early_wakeup_duration_ms - max_wakeup_time_ms;

                //simdbg("stdout", "Starting on timer in %" PRIu32 "\n", start);

                call OnTimer.startOneShotAt(now, start);
            }
        }
    }

    // OnTimer has just fired, start off timer
    void startOffTimer(uint32_t now)
    {
        if (!call OffTimer.isRunning())
        {
            const uint32_t start = early_wakeup_duration_ms + max_wakeup_time_ms;

            //simdbg("stdout", "Starting off timer 2 in %" PRIu32 "\n", start);
            call OffTimer.startOneShotAt(now, start);
        }
    }

    // Just received a message, consider when to turn off
    void startOffTimerFromMessage(uint32_t now)
    {
        // When a message is received, we should restart the off timer if it is running

        if (!call OffTimer.isRunning())
        {
            call OffTimer.startOneShotAt(now, max_wakeup_time_ms);
        }
    }

    command bool MessageTimingAnalysis.can_turn_off()
    {
        return call OnTimer.isRunning() && !call OffTimer.isRunning();
    }
}
