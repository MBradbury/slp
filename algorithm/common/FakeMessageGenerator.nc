
interface FakeMessageGenerator
{
	command void start(const void* original, uint8_t original_size);
	command void startLimited(const void* original, uint8_t size, uint32_t duration_ms);
	command void startRepeated(const void* original, uint8_t size, uint32_t duration_ms);

	command void stop();

	command void expireDuration();

	// Events that need to be implemented
	event uint32_t initialStartDelay();
	event uint32_t calculatePeriod();
	event void sendFakeMessage();

	// Events that can be listened for
	event void durationExpired(const void* original, uint8_t original_size);
}
