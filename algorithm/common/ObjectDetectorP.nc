
configuration ObjectDetectorP
{
	provides interface ObjectDetector;
}
implementation
{
	components ObjectDetectorImplP as App;

	ObjectDetector = App;

	// Timers
	components new TimerMilliC() as DetectionTimer;
	components new TimerMilliC() as ExpireTimer;

	App.DetectionTimer -> DetectionTimer;
	App.ExpireTimer -> ExpireTimer;

#ifdef USE_SERIAL_PRINTF
	components LocalTimeMilliC;
	
	App.LocalTime -> LocalTimeMilliC;
#endif
}
