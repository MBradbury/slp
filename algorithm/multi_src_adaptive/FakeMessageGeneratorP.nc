#include "Constants.h"

#include <Timer.h>

configuration FakeMessageGeneratorP
{
	provides interface FakeMessageGenerator;

	uses interface MetricLogging;

	uses interface AMSend as FakeSender;
	uses interface Packet;
}
implementation
{
	components FakeMessageGeneratorImplP as App;

	FakeMessageGenerator = App;

#ifndef TOSSIM
	components LocalTimeMilliC;
	
	App.LocalTime -> LocalTimeMilliC;
#endif

	App.MetricLogging = MetricLogging;

	components
		new TimerMilliC() as SendFakeTimer,
		new TimerMilliC() as DurationTimer;

	App.SendFakeTimer -> SendFakeTimer;
	App.DurationTimer -> DurationTimer;

	App.Packet = Packet;
	App.FakeSend = FakeSender;
}
