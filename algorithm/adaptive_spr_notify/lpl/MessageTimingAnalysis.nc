interface MessageTimingAnalysis
{
    command void expected_interval(uint32_t interval_ms);

    command void received(uint32_t timestamp_ms, bool valid_timestamp, bool is_new);

    command uint32_t last_group_start();
    command uint32_t next_group_wait();
    command uint32_t early_wakeup_duration();
    command uint32_t awake_duration();
}
