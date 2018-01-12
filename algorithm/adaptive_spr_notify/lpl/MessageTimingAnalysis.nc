interface MessageTimingAnalysis
{
    command void expected(uint32_t duration_ms, uint32_t period_ms, uint8_t source_type, uint32_t rcvd_timestamp);

    command void received(message_t* msg, const void* data, uint32_t timestamp_ms, bool is_new, uint8_t source_type);

    event void start_radio();
    event void stop_radio();

    command bool can_turn_off();
}
