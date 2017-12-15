interface SLPDutyCycle
{
    command void expected(uint32_t duration_ms, uint32_t period_ms, uint8_t source_type, uint32_t rcvd_timestamp);

    command void received_Normal(message_t* msg, const void* data, uint8_t flags, uint8_t source_type, uint32_t rcvd_timestamp);
    command void received_Fake(message_t* msg, const void* data, uint8_t flags, uint8_t source_type, uint32_t rcvd_timestamp);
}
