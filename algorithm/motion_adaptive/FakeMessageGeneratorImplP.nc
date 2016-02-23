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
	bool original_message_set = FALSE;
	bool should_send_choose = TRUE;

	bool is_expired = FALSE;

	// Network variables

	bool busy = FALSE;
	message_t packet;

	// Implementation

	command void FakeMessageGenerator.start(const AwayChooseMessage* original)
	{
		// Shouldn't start sending fake messages when already sending them
		assert(!(call SendFakeTimer.isRunning()));

		if (original != NULL)
		{
			original_message = *original;
			original_message_set = TRUE;
		}

		// The first fake message is to be sent half way through the period.
		// After this message is sent, all other messages are sent with an interval
		// of the period given. The aim here is to reduce the traffic at the start and
		// end of the TFS duration.
		call SendFakeTimer.startOneShot((signal FakeMessageGenerator.calculatePeriod()) / 2);
	}

	command void FakeMessageGenerator.startLimited(const AwayChooseMessage* original, uint32_t duration_ms)
	{
		call FakeMessageGenerator.start(original);

		call DurationTimer.startOneShot(duration_ms);

		simdbgverbose("FakeMessageGeneratorImplP", "SendFakeTimer started limited with a duration of %u ms.\n", duration_ms);
	}

	command void FakeMessageGenerator.stop(bool send_choose)
	{
		should_send_choose = send_choose;
		call DurationTimer.stop();
		call SendFakeTimer.stop();
		should_send_choose = TRUE;
	}

	default event uint32_t FakeMessageGenerator.calculatePeriod()
	{
		return 0;
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
		uint32_t period;

		simdbgverbose("FakeMessageGeneratorImplP", "SendFakeTimer fired.\n");

		send_fake_message();

		// It is possible that send_fake_message will lead to the node
		// becoming normal.
		if (!is_expired)
		{
			period = signal FakeMessageGenerator.calculatePeriod();

			if (period > 0)
			{
				call SendFakeTimer.startOneShot(period);
			}
		}
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
		is_expired = TRUE;
		call SendFakeTimer.stop();
		signal FakeMessageGenerator.durationExpired(&original_message, original_message_set, should_send_choose);
	}
}
