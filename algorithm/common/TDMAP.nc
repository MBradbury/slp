
configuration TDMAP
{
	provides interface TDMA;

	uses interface MetricLogging;
    uses interface NodeType;
}
implementation
{
	components TDMAImplP as App;
	App.TDMA = TDMA;

	App.MetricLogging = MetricLogging;
    App.NodeType = NodeType;

    components MainC;
    MainC.SoftwareInit -> App;

	// Timers
    components
    	new TimerMilliC() as DissemTimer,
        new TimerMilliC() as PreSlotTimer,
        new TimerMilliC() as SlotTimer,
        new TimerMilliC() as PostSlotTimer,
        new TimerMilliC() as TimesyncTimer;

    App.DissemTimer -> DissemTimer;
    App.PreSlotTimer -> PreSlotTimer;
    App.SlotTimer -> SlotTimer;
    App.PostSlotTimer -> PostSlotTimer;
    App.TimesyncTimer -> TimesyncTimer;

    components TimeSyncC;
    MainC.SoftwareInit -> TimeSyncC;
    TimeSyncC.Boot -> MainC;
    App.TimeSyncMode -> TimeSyncC;
    App.TimeSyncNotify -> TimeSyncC;
    App.GlobalTime -> TimeSyncC;

    /*App.GlobalTime = GlobalTime;*/
}
