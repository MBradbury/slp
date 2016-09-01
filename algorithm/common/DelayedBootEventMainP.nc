
configuration DelayedBootEventMainP {
	provides interface Boot;
}
implementation {
	components DelayedBootEventMainImplP;

	components MainC;

	DelayedBootEventMainImplP.OriginalBoot -> MainC;

	components new TimerMilliC() as DelayTimer;

	DelayedBootEventMainImplP.DelayTimer -> DelayTimer;

	Boot = DelayedBootEventMainImplP;
}
