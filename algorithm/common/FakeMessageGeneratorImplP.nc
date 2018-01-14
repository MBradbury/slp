#include "MetricLogging.h"

module FakeMessageGeneratorImplP
{
	provides
	{
		interface FakeMessageGenerator;
	}
	uses
	{
		interface LocalTime<TMilli>;

		interface Packet;

		interface Timer<TMilli> as SendFakeTimer;
		interface Timer<TMilli> as DurationTimer;

		interface MetricLogging;
		interface MetricHelpers;
	}
}
implementation
{
	message_t message;

	// Implementation

	command void FakeMessageGenerator.start(const void* original, uint8_t size, uint32_t become_fake_time)
	{
		call Packet.clear(&message);
		call Packet.setPayloadLength(&message, size);
		memcpy(call Packet.getPayload(&message, size), original, size);

		call SendFakeTimer.startOneShotAt(become_fake_time, signal FakeMessageGenerator.initialStartDelay());

		simdbgverbose("stdout", "SendFakeTimer started at %" PRIu32 " one shot.\n", become_fake_time);
	}

	command void FakeMessageGenerator.startLimited(const void* original, uint8_t size, uint32_t duration_ms, uint32_t become_fake_time)
	{
		call FakeMessageGenerator.start(original, size, become_fake_time);

		call DurationTimer.startOneShotAt(become_fake_time, duration_ms);

		simdbgverbose("stdout", "SendFakeTimer started at %" PRIu32 " limited with a duration of %" PRIu32 " ms.\n", become_fake_time, duration_ms);
	}

	command void FakeMessageGenerator.startRepeated(const void* original, uint8_t size, uint32_t duration_ms, uint32_t become_fake_time)
	{
		call FakeMessageGenerator.start(original, size, become_fake_time);

		call DurationTimer.startPeriodicAt(become_fake_time, duration_ms);

		simdbgverbose("stdout", "SendFakeTimer started at %" PRIu32 " repeated with a duration of %" PRIu32 " ms.\n", become_fake_time, duration_ms);
	}

	command void FakeMessageGenerator.stop()
	{
		call DurationTimer.stop();
		call SendFakeTimer.stop();
	}

	event void SendFakeTimer.fired()
	{
		// Store the start time, so we can account for the time spend in calculatePeriod
		// This helps avoid time drift between fake send events
		const uint32_t start_time = call SendFakeTimer.gett0() + call SendFakeTimer.getdt();

		const uint32_t period = signal FakeMessageGenerator.calculatePeriod();

		if (period > 0)
		{
			call SendFakeTimer.startOneShotAt(start_time, period);
		}
		else
		{
			ERROR_OCCURRED(ERROR_SEND_FAKE_PERIOD_ZERO, "SendFakeTimer stopped as the next period was calculated to be 0.\n");
		}

		simdbgverbose("stdout", "SendFakeTimer fired at %" PRIu32 ", started for %" PRIu32 ".\n", start_time, start_time+period);

		signal FakeMessageGenerator.sendFakeMessage();
	}

	event void DurationTimer.fired()
	{
		const uint32_t expired_at = call DurationTimer.gett0() + call DurationTimer.getdt();

		simdbgverbose("stdout", "DurationTimer fired at %" PRIu32 ".\n", expired_at);

		call FakeMessageGenerator.expireDuration(expired_at);
	}

	command void FakeMessageGenerator.expireDuration(uint32_t duration_expired_at)
	{
		const uint8_t payload_length = call Packet.payloadLength(&message);
		const void* payload = call Packet.getPayload(&message, payload_length);

		signal FakeMessageGenerator.durationExpired(payload, payload_length, duration_expired_at);
	}
}
