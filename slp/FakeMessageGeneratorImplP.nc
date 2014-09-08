#include "FakeMessage.h"

#define DEBUG_PREFIX "%s: [%s] "
#define DEBUG_ARGS sim_time_string(), (send_forever ? "PermFS====" : "TempFS====")

#define mydbg(type, message, ...) dbg(type, DEBUG_PREFIX message, DEBUG_ARGS, ##__VA_ARGS__)
#define myerr(type, message, ...) dbgerror(type, DEBUG_PREFIX message, DEBUG_ARGS, ##__VA_ARGS__)

module FakeMessageGeneratorImplP
{
	provides
	{
		interface FakeMessageGenerator;
	}
	uses
	{
		interface Timer<TMilli> as GenerateFakeTimer;

		interface Packet;
		interface AMSend as FakeSend;
	}
}
implementation
{
	AwayChooseMessage original_message;

	uint32_t messages_to_send;
	bool send_forever;

	// Network variables

	bool busy = FALSE;
	message_t packet;

	// Implementation

	command void FakeMessageGenerator.start(const AwayChooseMessage* original, uint32_t period_ms)
	{
		original_message = *original;

		call GenerateFakeTimer.startPeriodic(period_ms);

		messages_to_send = UINT32_MAX;
		send_forever = TRUE;
	}

	command void FakeMessageGenerator.startLimited(const AwayChooseMessage* original, uint32_t period_ms, uint32_t to_send)
	{
		original_message = *original;

		call FakeMessageGenerator.start(original, period_ms);

		messages_to_send = to_send;
		send_forever = FALSE;

		mydbg("FakeMessageGeneratorImplP", "GenerateFakeTimer started limited with %u messages.\n", messages_to_send);
	}

	command void FakeMessageGenerator.stop()
	{
		call GenerateFakeTimer.stop();
	}
	
	default event void FakeMessageGenerator.sent(error_t error)
	{
	}

	bool generate_fake_message()
	{
		error_t status;

		if (!busy)
		{
			FakeMessage* message = (FakeMessage*)(call Packet.getPayload(&packet, sizeof(FakeMessage)));
			if (message == NULL)
			{
				myerr("FakeMessageGeneratorImplP", "Packet has no payload, or payload is too large.\n");
				return FALSE;
			}

			signal FakeMessageGenerator.generateFakeMessage(message);

			status = call FakeSend.send(AM_BROADCAST_ADDR, &packet, sizeof(FakeMessage));
			if (status == SUCCESS)
			{
				busy = TRUE;
			}

			signal FakeMessageGenerator.sent(status);

			return status == SUCCESS;
		}
		else
		{
			signal FakeMessageGenerator.sent(EBUSY);

			myerr("SourceBroadcasterC", "BroadcastAway busy, not forwarding Away message.\n");
			return FALSE;
		}
	}

	event void GenerateFakeTimer.fired()
	{
		mydbg("FakeMessageGeneratorImplP", "GenerateFakeTimer fired.\n");

		if (messages_to_send >= 1)
		{
			if (generate_fake_message())
			{
				if (!send_forever)
					messages_to_send -= 1;
			}
		}

		// Sent all the messages that we should have sent
		if (messages_to_send == 0)
		{
			call GenerateFakeTimer.stop();
			signal FakeMessageGenerator.sendDone(&original_message);
		}
	}

	event void FakeSend.sendDone(message_t* msg, error_t error)
	{
		mydbg("FakeMessageGeneratorImplP", "FakeSend sendDone with status %i.\n", error);

		if (&packet == msg)
		{
			busy = FALSE;
		}
	}
}
