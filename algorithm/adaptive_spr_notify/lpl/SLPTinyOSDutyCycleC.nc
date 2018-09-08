
#warning "*** USING TinyOS SLP DUTY CYCLE LOW POWER COMMUNICATIONS ***"

configuration SLPTinyOSDutyCycleC
{
    provides
    {
        interface LowPowerListening;
        interface Send;
        interface Receive;
        interface SplitControl;

        interface SLPDutyCycle;
    }

    uses interface Send as SubSend;
    uses interface Receive as SubReceive;
    uses interface SplitControl as SubControl;
}
implementation
{
    components DummyDutyCycleP;
    SLPDutyCycle = DummyDutyCycleP;

    components LplC;

    LowPowerListening = LplC;
    Send = LplC;
    Receive = LplC;
    SplitControl = LplC;
    

    LplC.SubSend = SubSend;
    LplC.SubReceive = SubReceive;
    LplC.SubControl = SubControl;

    components MetricLoggingP as MetricLogging;
    DummyDutyCycleP.MetricLogging -> MetricLogging;
}
