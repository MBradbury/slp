
#warning "*** USING Dummy SLP DUTY CYCLE LOW POWER COMMUNICATIONS ***"

configuration DummyDutyCycleC
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
    components DummyLplC;
    components DummyDutyCycleP;

    LowPowerListening = DummyLplC;
    Send = DummyLplC;
    Receive = DummyLplC;
    SplitControl = DummyLplC;
    SLPDutyCycle = DummyDutyCycleP;

    DummyLplC.SubSend = SubSend;
    DummyLplC.SubReceive = SubReceive;
    DummyLplC.SubControl = SubControl;

    components MetricLoggingP as MetricLogging;
    DummyDutyCycleP.MetricLogging -> MetricLogging;
}
