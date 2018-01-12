
#include "../Constants.h"
#include "../FakeMessage.h"

#include "SLPDutyCycleFlags.h"

module DummyDutyCycleP
{
    provides
    {
        interface SLPDutyCycle;
    }
    uses
    {
        interface MetricLogging;
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
        /*const bool is_new = (flags & SLP_DUTY_CYCLE_IS_NEW) != 0;
        const bool is_first_fake = (flags & SLP_DUTY_CYCLE_IS_FIRST_FAKE) != 0;
        const bool is_adjacent = (flags & SLP_DUTY_CYCLE_IS_ADJACENT_TO_FAKE) != 0;

        const FakeMessage* mdata = (const FakeMessage*)data;

        LOG_STDOUT(0, "received FAKE at=%" PRIu32 " from=%" PRIu16 " count=%" PRIu16 " new=%" PRIu8 " first=%" PRIu8 " ajd=%" PRIu8 "\n",
            rcvd_timestamp, mdata->source_id, mdata->ultimate_sender_fake_count, is_new, is_first_fake, is_adjacent);*/
    }
}
