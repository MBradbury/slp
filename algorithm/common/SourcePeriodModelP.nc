
configuration SourcePeriodModelP
{
	provides interface SourcePeriodModel;

	uses interface SourcePeriodConverter;
}
implementation
{
	components SourcePeriodModelImplP as App;

	SourcePeriodModel = App;

	App.SourcePeriodConverter = SourcePeriodConverter;

	// LocalTime
	components LocalTimeMilliC;
	
	App.LocalTime -> LocalTimeMilliC;

	//Timers
	components new TimerMilliC() as EventTimer;

	App.EventTimer -> EventTimer;
}
