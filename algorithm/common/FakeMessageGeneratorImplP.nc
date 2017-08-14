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

	command void FakeMessageGenerator.start(const void* original, uint8_t size)
	{
		call Packet.clear(&message);
		call Packet.setPayloadLength(&message, size);
		memcpy(call Packet.getPayload(&message, size), original, size);

		call SendFakeTimer.startOneShot(signal FakeMessageGenerator.initialStartDelay());

		simdbgverbose("FakeMessageGeneratorImplP", "SendFakeTimer started one shot.\n");
	}

	command void FakeMessageGenerator.startLimited(const void* original, uint8_t size, uint32_t duration_ms)
	{
		call FakeMessageGenerator.start(original, size);

		call DurationTimer.startOneShot(duration_ms);

		simdbgverbose("FakeMessageGeneratorImplP", "SendFakeTimer started limited with a duration of %u ms.\n", duration_ms);
	}

	command void FakeMessageGenerator.startRepeated(const void* original, uint8_t size, uint32_t duration_ms)
	{
		call FakeMessageGenerator.start(original, size);

		call DurationTimer.startPeriodic(duration_ms);

		simdbgverbose("FakeMessageGeneratorImplP", "SendFakeTimer started limited with a duration of %u ms.\n", duration_ms);
	}

	command void FakeMessageGenerator.stop(void)
	{
		call DurationTimer.stop();
		call SendFakeTimer.stop();
	}

	event void SendFakeTimer.fired(void)
	{
		uint32_t period, start_time;

		// Store the start time, so we can account for the time spend in calculatePeriod
		// This helps avoid time drift between fake send events
		start_time = call LocalTime.get();

		period = signal FakeMessageGenerator.calculatePeriod();

		if (period > 0)
		{
			call SendFakeTimer.startOneShotAt(start_time, period);
		}
		else
		{
			ERROR_OCCURRED(ERROR_SEND_FAKE_PERIOD_ZERO, "SendFakeTimer stopped as the next period was calculated to be 0.\n");
		}

		simdbgverbose("FakeMessageGeneratorImplP", "SendFakeTimer fired.\n");

		signal FakeMessageGenerator.sendFakeMessage();
	}

	event void DurationTimer.fired(void)
	{
		simdbgverbose("FakeMessageGeneratorImplP", "DurationTimer fired.\n");

		call FakeMessageGenerator.expireDuration();
	}

	command void FakeMessageGenerator.expireDuration(void)
	{
		const uint8_t payload_length = call Packet.payloadLength(&message);
		const void* payload = call Packet.getPayload(&message, payload_length);

		signal FakeMessageGenerator.durationExpired(payload, payload_length);
	}
}
