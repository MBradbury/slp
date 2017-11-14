interface SLPDutyCycle
{
    command void received_Normal(message_t* msg, uint32_t expected_delay);
    command void received_Fake(message_t* msg, uint32_t expected_delay);
}
