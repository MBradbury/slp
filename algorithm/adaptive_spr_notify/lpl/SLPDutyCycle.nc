interface SLPDutyCycle
{
    command void normal_expected_interval(uint32_t expected_interval_ms);
    command void fake_expected_interval(uint32_t expected_interval_ms);

    command void received_Normal(message_t* msg, bool is_new);
    command void received_Fake(message_t* msg, bool is_new);
}
