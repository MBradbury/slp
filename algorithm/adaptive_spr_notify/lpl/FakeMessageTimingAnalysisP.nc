
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

    components LocalTimeMilliC;
    Impl.LocalTime -> LocalTimeMilliC;

    components new TimerMilliC() as TempDurationTimerC;
    components new TimerMilliC() as TempOnTimerC;
    components new TimerMilliC() as TempOffTimerC;
    Impl.TempOffTimer -> TempOffTimerC;
    Impl.TempOnTimer -> TempOnTimerC;
    Impl.TempDurationTimer -> TempDurationTimerC;

    components new TimerMilliC() as PermOnTimerC;
    components new TimerMilliC() as PermOffTimerC;
    Impl.PermOffTimer -> PermOffTimerC;
    Impl.PermOnTimer -> PermOnTimerC;

    components new TimerMilliC() as PermDetectTimer;
    Impl.PermDetectTimer -> PermDetectTimer;

}
