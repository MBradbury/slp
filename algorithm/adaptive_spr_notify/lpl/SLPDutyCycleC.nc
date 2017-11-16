
#warning "*** USING SLP DUTY CYCLE LOW POWER COMMUNICATIONS ***"

configuration SLPDutyCycleC
{
    provides
    {
        interface LowPowerListening;
        interface Send;
        interface Receive;
        interface SplitControl;
        interface SLPDutyCycle;
    }
    uses
    {
        interface Send as SubSend;
        interface Receive as SubReceive;
        interface SplitControl as SubControl;
    }
}
implementation
{
    components SLPDutyCycleP;
    LowPowerListening = SLPDutyCycleP;
    Send = SLPDutyCycleP;
    Receive = SLPDutyCycleP;
    SplitControl = SLPDutyCycleP;
    SLPDutyCycle = SLPDutyCycleP;

    SLPDutyCycleP.SubSend = SubSend;
    SLPDutyCycleP.SubReceive = SubReceive;
    SLPDutyCycleP.SubControl = SubControl;

    components MainC;
    MainC.SoftwareInit -> SLPDutyCycleP;

    components LedsC;
    SLPDutyCycleP.Leds -> LedsC;

    components RandomC;
    SLPDutyCycleP.Random -> RandomC;

    components MetricLoggingP as MetricLogging;
    SLPDutyCycleP.MetricLogging -> MetricLogging;

    // CC2420 components
    components CC2420RadioC;
    components CC2420CsmaC;
    components CC2420PacketC;
    components CC2420TransmitC;
    components CC2420ReceiveC;

    SLPDutyCycleP.Resend -> CC2420TransmitC;
    SLPDutyCycleP.PacketAcknowledgements -> CC2420RadioC;
    SLPDutyCycleP.CC2420PacketBody -> CC2420PacketC;
    SLPDutyCycleP.RadioBackoff -> CC2420CsmaC;
    SLPDutyCycleP.EnergyIndicator -> CC2420TransmitC.EnergyIndicator;
    //SLPDutyCycleP.ByteIndicator -> CC2420TransmitC.ByteIndicator;
    SLPDutyCycleP.PacketIndicator -> CC2420ReceiveC.PacketIndicator;

    components new TimerMilliC() as OnTimerC;
    components new TimerMilliC() as OffTimerC;
    components new TimerMilliC() as SendDoneTimerC;
    SLPDutyCycleP.OffTimer -> OffTimerC;
    SLPDutyCycleP.SendDoneTimer -> SendDoneTimerC;
    SLPDutyCycleP.OnTimer -> OnTimerC;

    components SystemLowPowerListeningC;  
    SLPDutyCycleP.SystemLowPowerListening -> SystemLowPowerListeningC;

    components new StateC() as SendStateC;
    components new StateC() as RadioPowerStateC;
    components new StateC() as SplitControlStateC;
    SLPDutyCycleP.SendState -> SendStateC;
    SLPDutyCycleP.RadioPowerState -> RadioPowerStateC;
    SLPDutyCycleP.SplitControlState -> SplitControlStateC;

    components ActiveMessageC;
    SLPDutyCycleP.PacketTimeStamp -> ActiveMessageC;

    components LocalTimeMilliC;
    SLPDutyCycleP.LocalTime -> LocalTimeMilliC;

    components new MessageTimingAnalysisC() as NormalMessageTimingAnalysis;
    components new MessageTimingAnalysisC() as FakeMessageTimingAnalysis;
    SLPDutyCycleP.NormalMessageTimingAnalysis -> NormalMessageTimingAnalysis;
    SLPDutyCycleP.FakeMessageTimingAnalysis -> FakeMessageTimingAnalysis;
}
