
interface FakeMessageGenerator
{
	command void start(const void* original, uint8_t original_size, uint32_t become_fake_time);
	command void startLimited(const void* original, uint8_t size, uint32_t duration_ms, uint32_t become_fake_time);
	command void startRepeated(const void* original, uint8_t size, uint32_t duration_ms, uint32_t become_fake_time);

	command void stop(void);

	command void expireDuration(uint32_t duration_expired_at);

	// Events that need to be implemented
	event uint32_t initialStartDelay(void);
	event uint32_t calculatePeriod(void);
	event void sendFakeMessage(void);

	// Events that can be listened for
	event void durationExpired(const void* original, uint8_t original_size, uint32_t duration_expired_at);
}
