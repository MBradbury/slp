
configuration DelayedBootEventMainP {
	provides interface Boot;
}
implementation {
	components DelayedBootEventMainImplP;

	components MainC;

	DelayedBootEventMainImplP.OriginalBoot -> MainC;

#if defined(TESTBED)
	components new TimerMilliC() as DelayTimer;

	DelayedBootEventMainImplP.DelayTimer -> DelayTimer;
#endif

	Boot = DelayedBootEventMainImplP;
}
