#include "Constants.h"

#include <Timer.h>

configuration FakeMessageGeneratorP
{
	provides interface FakeMessageGenerator;
}
implementation
{
	components FakeMessageGeneratorImplP as App;

	FakeMessageGenerator = App;

	components new TimerMilliC() as GenerateFakeTimer;

	App.GenerateFakeTimer -> GenerateFakeTimer;

	components new AMSenderC(FAKE_CHANNEL) as FakeSender;

	App.Packet -> FakeSender;
	App.FakeSend -> FakeSender;
}

