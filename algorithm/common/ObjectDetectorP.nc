
configuration ObjectDetectorP
{
	provides interface ObjectDetector;

	uses interface NodeType;
}
implementation
{
	components ObjectDetectorImplP as App;
	ObjectDetector = App;
	App.NodeType = NodeType;

	// Timers
	components new TimerMilliC() as DetectionTimer;
	components new TimerMilliC() as ExpireTimer;

	App.DetectionTimer -> DetectionTimer;
	App.ExpireTimer -> ExpireTimer;

#ifdef USE_SERIAL_PRINTF
	components LocalTimeMilliC;
	
	App.LocalTime -> LocalTimeMilliC;
#endif

	components MainC;
	MainC.SoftwareInit -> App;
}
