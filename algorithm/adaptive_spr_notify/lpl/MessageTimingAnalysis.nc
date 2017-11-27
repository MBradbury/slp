interface MessageTimingAnalysis
{
    command void expected_interval(uint32_t interval_ms);

    command void received(uint32_t timestamp_ms, bool valid_timestamp, bool is_new);

    command uint32_t last_group_start();
    command uint32_t next_group_wait();
    command uint32_t early_wakeup_duration();
    command uint32_t awake_duration();

    event void on_timer_fired();
    event void off_timer_fired();

    command bool waiting_to_turn_on();
    command bool waiting_to_turn_off();
}
