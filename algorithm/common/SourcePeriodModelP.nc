
configuration SourcePeriodModelP
{
	provides interface SourcePeriodModel;
}
implementation
{
	components SourcePeriodModelImplP as App;

	SourcePeriodModel = App;

	// LocalTime
	components LocalTimeMilliC;
	
	App.LocalTime -> LocalTimeMilliC;
}
