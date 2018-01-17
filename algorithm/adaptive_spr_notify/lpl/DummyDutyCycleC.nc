
#warning "*** USING Dummy SLP DUTY CYCLE LOW POWER COMMUNICATIONS ***"

configuration DummyDutyCycleC
{
    provides
    {
#ifdef LOW_POWER_LISTENING
        interface LowPowerListening;
        interface Send;
        interface Receive;
        interface SplitControl;
#endif
        interface SLPDutyCycle;
    }

#ifdef LOW_POWER_LISTENING
    uses interface Send as SubSend;
    uses interface Receive as SubReceive;
    uses interface SplitControl as SubControl;
#endif
}
implementation
{
    components DummyDutyCycleP;
    SLPDutyCycle = DummyDutyCycleP;

#ifdef LOW_POWER_LISTENING

    components DummyLplC;

    LowPowerListening = DummyLplC;
    Send = DummyLplC;
    Receive = DummyLplC;
    SplitControl = DummyLplC;
    

    DummyLplC.SubSend = SubSend;
    DummyLplC.SubReceive = SubReceive;
    DummyLplC.SubControl = SubControl;
#endif

    components MetricLoggingP as MetricLogging;
    DummyDutyCycleP.MetricLogging -> MetricLogging;
}
