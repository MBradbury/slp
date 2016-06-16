#include "ChooseMessage.h"

interface FakeMessageGenerator
{
	command void start(const ChooseMessage* original_message);
	command void startLimited(const ChooseMessage* original_message, uint32_t duration_ms);
	command void startRepeated(const ChooseMessage* original_message, uint32_t duration_ms);

	command void stop();

	command void expireDuration();

	event uint32_t calculatePeriod();
	
	event void generateFakeMessage(FakeMessage* message);

	event void sent(error_t error, const FakeMessage* message);

	event void durationExpired(const ChooseMessage* original_message);
}
