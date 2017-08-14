
configuration ReadRssiAppC
{
}

implementation
{
	// The application
	components ReadRssiC as App;

	// Low levels events such as boot and LED control
	components DelayedBootEventMainP as MainC;
	components LedsWhenGuiC as LedsC;
	
	App.Boot -> MainC;
	App.Leds -> LedsC;

	components MetricLoggingP as MetricLogging;
	App.MetricLogging -> MetricLogging;
	
	components MetricHelpersP as MetricHelpers;
	App.MetricHelpers -> MetricHelpers;

	// Radio Control
	components ActiveMessageC;

	App.RadioControl -> ActiveMessageC;

	// CC2420
	components CC2420ControlC;

	App.ReadRssi -> CC2420ControlC.ReadRssi;
	App.Config -> CC2420ControlC.CC2420Config;

	// Time
	//components LocalTimeMilliC;
	//App.LocalTime -> LocalTimeMilliC;
}
