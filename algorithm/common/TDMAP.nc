
configuration TDMAP
{
	provides interface TDMA;

	uses interface MetricLogging;
}
implementation
{
	components TDMAImplP as App;
	App.TDMA = TDMA;

	App.MetricLogging = MetricLogging;

    components MainC;
    Main.SoftwareInit -> App;

	components LocalTimeMilliC;
    App.LocalTime -> LocalTimeMilliC;

	// Timers
    components
    	new TimerMilliC() as DissemTimer,
        new TimerMilliC() as PreSlotTimer,
        new TimerMilliC() as SlotTimer,
        new TimerMilliC() as PostSlotTimer;

    App.DissemTimer -> DissemTimer;
    App.PreSlotTimer -> PreSlotTimer;
    App.SlotTimer -> SlotTimer;
    App.PostSlotTimer -> PostSlotTimer;
}
