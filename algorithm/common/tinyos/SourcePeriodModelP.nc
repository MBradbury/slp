
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

	//Timers
	components new TimerMilliC() as EventTimer;

	App.EventTimer -> EventTimer;
}
