
module DummyDutyCycleP
{
    provides
    {
        interface SLPDutyCycle;
    }
}
implementation
{
    /**************** SLPDutyCycle *****************/
    command void SLPDutyCycle.expected(uint32_t duration_ms, uint32_t period_ms, uint8_t source_type, uint32_t rcvd_timestamp)
    {
    }

    command void SLPDutyCycle.received_Normal(message_t* msg, const void* data, uint8_t flags, uint8_t source_type, uint32_t rcvd_timestamp)
    {
    }

    command void SLPDutyCycle.received_Fake(message_t* msg, const void* data, uint8_t flags, uint8_t source_type, uint32_t rcvd_timestamp)
    {
    }
}
