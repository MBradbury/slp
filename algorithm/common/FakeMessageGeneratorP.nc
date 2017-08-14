
configuration FakeMessageGeneratorP
{
	provides interface FakeMessageGenerator;

	uses interface Packet;

	uses interface MetricLogging;
	uses interface MetricHelpers;
}
implementation
{
	components FakeMessageGeneratorImplP as App;

	FakeMessageGenerator = App;

	App.Packet = Packet;
	App.MetricLogging = MetricLogging;
	App.MetricHelpers = MetricHelpers;

	components LocalTimeMilliC;
	
	App.LocalTime -> LocalTimeMilliC;

	components
		new TimerMilliC() as SendFakeTimer,
		new TimerMilliC() as DurationTimer;

	App.SendFakeTimer -> SendFakeTimer;
	App.DurationTimer -> DurationTimer;
}
