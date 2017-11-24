
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
    command void SLPDutyCycle.normal_expected_interval(uint32_t expected_interval_ms)
    {
    }

    command void SLPDutyCycle.fake_expected_interval(uint32_t expected_interval_ms)
    {
    }

    command void SLPDutyCycle.received_Normal(message_t* msg, bool is_new)
    {
    }

    command void SLPDutyCycle.received_Fake(message_t* msg, bool is_new)
    {
    }
}
