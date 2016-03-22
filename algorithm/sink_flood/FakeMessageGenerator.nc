#include "AwayChooseMessage.h"

interface FakeMessageGenerator
{
	command void start(const AwayMessage* original_message);
	command void startLimited(const AwayMessage* original_message, uint32_t duration_ms);
	command void startRepeated(const AwayMessage* original_message, uint32_t duration_ms);

	command void stop();

	command void expireDuration();

	event uint32_t calculatePeriod();
	
	event void generateFakeMessage(FakeMessage* message);

	event void sent(error_t error, const FakeMessage* message);

	event void durationExpired(const AwayMessage* original_message);
}
