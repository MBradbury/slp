
generic configuration FakeMessageTimingAnalysisP()
{
    provides interface MessageTimingAnalysis;
}
implementation
{
    components new FakeMessageTimingAnalysisImplP() as Impl;
    Impl.MessageTimingAnalysis = MessageTimingAnalysis;

    components MainC;
    Impl.Init <- MainC.SoftwareInit;

    components MetricLoggingP as MetricLogging;
    Impl.MetricLogging -> MetricLogging;

    components new TimerMilliC() as TempOnTimerC;
    components new TimerMilliC() as TempOffTimerC;
    Impl.TempOffTimer -> TempOffTimerC;
    Impl.TempOnTimer -> TempOnTimerC;

    components new TimerMilliC() as PermOnTimerC;
    components new TimerMilliC() as PermOffTimerC;
    Impl.PermOffTimer -> PermOffTimerC;
    Impl.PermOnTimer -> PermOnTimerC;

    components new TimerMilliC() as ChooseOnTimerC;
    components new TimerMilliC() as ChooseOffTimerC;
    Impl.ChooseOffTimer -> ChooseOffTimerC;
    Impl.ChooseOnTimer -> ChooseOnTimerC;

    components new TimerMilliC() as DurationOnTimerC;
    components new TimerMilliC() as DurationOffTimerC;
    Impl.DurationOffTimer -> DurationOffTimerC;
    Impl.DurationOnTimer -> DurationOnTimerC;


    //components new TimerMilliC() as PermDetectTimer;
    //Impl.PermDetectTimer -> PermDetectTimer;

}
