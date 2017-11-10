
configuration DelayedBootEventMainP {
	provides interface Boot;

	uses interface Init as SoftwareInit;
}
implementation {
	components DelayedBootEventMainImplP;

	components MainC;
	MainC.SoftwareInit = SoftwareInit;

	DelayedBootEventMainImplP.OriginalBoot -> MainC.Boot;
    Boot = DelayedBootEventMainImplP.Boot;

#if defined(TESTBED)
	components new TimerMilliC() as DelayTimer;
	DelayedBootEventMainImplP.DelayTimer -> DelayTimer;
#endif

    components MetricLoggingP as MetricLogging;
    DelayedBootEventMainImplP.MetricLogging -> MetricLogging;
}
