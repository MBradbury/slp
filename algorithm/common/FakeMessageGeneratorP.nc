
configuration FakeMessageGeneratorP
{
	provides interface FakeMessageGenerator;

	uses interface Packet;

	uses interface MetricLogging;
}
implementation
{
	components FakeMessageGeneratorImplP as App;

	FakeMessageGenerator = App;

	App.Packet = Packet;
	App.MetricLogging = MetricLogging;

	components LocalTimeMilliC;
	
	App.LocalTime -> LocalTimeMilliC;

	components
		new TimerMilliC() as SendFakeTimer,
		new TimerMilliC() as DurationTimer;

	App.SendFakeTimer -> SendFakeTimer;
	App.DurationTimer -> DurationTimer;
}
