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

	components
		new TimerMilliC() as SendFakeTimerInitial,
		new TimerMilliC() as SendFakeTimer;

	App.SendFakeTimerInitial -> SendFakeTimerInitial;
	App.SendFakeTimer -> SendFakeTimer;

	components new TimerMilliC() as DurationTimer;

	App.DurationTimer -> DurationTimer;

	components new AMSenderC(FAKE_CHANNEL) as FakeSender;

	App.Packet -> FakeSender;
	App.FakeSend -> FakeSender;
}
