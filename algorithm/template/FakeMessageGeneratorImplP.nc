#include "FakeMessage.h"

module FakeMessageGeneratorImplP
{
	provides
	{
		interface FakeMessageGenerator;
	}
	uses
	{
		interface Timer<TMilli> as SendFakeTimer;

		interface Timer<TMilli> as DurationTimer;

		interface Packet;
		interface AMSend as FakeSend;
	}
}
implementation
{
	AwayChooseMessage original_message;

	// Network variables

	bool busy = FALSE;
	message_t packet;

	// Implementation

	command void FakeMessageGenerator.start(const AwayChooseMessage* original, uint32_t period_ms)
	{
		original_message = *original;

		call SendFakeTimer.startPeriodic(period_ms);
	}

	command void FakeMessageGenerator.startLimited(const AwayChooseMessage* original, uint32_t period_ms, uint32_t duration_ms)
	{
		call FakeMessageGenerator.start(original, period_ms);

		call DurationTimer.startOneShot(duration_ms);

		simdbgverbose("FakeMessageGeneratorImplP", "SendFakeTimer started limited with a duration of %u ms.\n", duration_ms);
	}

	command void FakeMessageGenerator.stop()
	{
		call DurationTimer.stop();
		call SendFakeTimer.stop();
	}
	
	default event void FakeMessageGenerator.sent(error_t error, const FakeMessage* message)
	{
	}

	bool send_fake_message()
	{
		error_t status;
		FakeMessage message;

		signal FakeMessageGenerator.generateFakeMessage(&message);

		if (!busy)
		{
			void* const void_tosend = call Packet.getPayload(&packet, sizeof(FakeMessage));
			FakeMessage* const tosend = (FakeMessage*)void_tosend;
			if (tosend == NULL)
			{
				simdbgerror("FakeMessageGeneratorImplP", "Packet has no payload, or payload is too large.\n");
				return FALSE;
			}

			*tosend = message;

			status = call FakeSend.send(AM_BROADCAST_ADDR, &packet, sizeof(FakeMessage));
			if (status == SUCCESS)
			{
				busy = TRUE;
			}

			signal FakeMessageGenerator.sent(status, &message);

			return status == SUCCESS;
		}
		else
		{
			signal FakeMessageGenerator.sent(EBUSY, &message);

			simdbgerror("FakeMessageGeneratorImplP", "BroadcastAway busy, not forwarding Away message.\n");
			return FALSE;
		}
	}

	event void SendFakeTimer.fired()
	{
		simdbgverbose("FakeMessageGeneratorImplP", "SendFakeTimer fired.\n");

		send_fake_message();
	}

	event void FakeSend.sendDone(message_t* msg, error_t error)
	{
		simdbgverbose("FakeMessageGeneratorImplP", "FakeSend sendDone with status %i.\n", error);

		if (&packet == msg)
		{
			busy = FALSE;
		}
	}

	event void DurationTimer.fired()
	{
		simdbgverbose("FakeMessageGeneratorImplP", "DurationTimer fired.\n");

		call FakeMessageGenerator.expireDuration();
	}

	command void FakeMessageGenerator.expireDuration()
	{
		call SendFakeTimer.stop();
		signal FakeMessageGenerator.durationExpired(&original_message);
	}
}
