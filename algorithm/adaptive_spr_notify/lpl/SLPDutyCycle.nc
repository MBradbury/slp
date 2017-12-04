interface SLPDutyCycle
{
    command void expected(uint32_t duration_ms, uint32_t period_ms, uint8_t source_type);

    command void received_Normal(message_t* msg, bool is_new, uint8_t source_type);
    command void received_Fake(message_t* msg, bool is_new, uint8_t source_type);
}
