
configuration TDMAMultiSlotP
{
	provides interface TDMAMultiSlot;

	uses interface MetricLogging;
}
implementation
{
    components TDMAMultiSlotImplP as App;

    App.TDMAMultiSlot = TDMAMultiSlot;

    App.MetricLogging = MetricLogging;

    components MainC;

    App.Init <- MainC;

	components LocalTimeMilliC;

    App.LocalTime -> LocalTimeMilliC;

    // Timers
    components
        new TimerMilliC() as DissemTimer,
        new TimerMilliC() as SlotTimer,
        new TimerMilliC() as NonSlotTimer;

    App.DissemTimer -> DissemTimer;
    App.SlotTimer -> SlotTimer;
    App.NonSlotTimer -> NonSlotTimer;
}
