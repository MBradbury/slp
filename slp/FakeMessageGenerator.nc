#include "AwayChooseMessage.h"

interface FakeMessageGenerator
{
	command void start(const AwayChooseMessage* original_message, uint32_t period_ms);
	command void startLimited(const AwayChooseMessage* original_message, uint32_t period_ms, uint32_t to_send);

	command void stop();
	
	event error_t generateFakeMessage(FakeMessage* message);

	event void sent(error_t error);

	event void sendDone(const AwayChooseMessage* original_message);
}
