
generic configuration MessageTimingAnalysisP()
{
    provides interface MessageTimingAnalysis;
}
implementation
{
    components new MessageTimingAnalysisImplP() as Impl;
    Impl.MessageTimingAnalysis = MessageTimingAnalysis;

    components MainC;
    Impl.Init <- MainC.SoftwareInit;

    components MetricLoggingP as MetricLogging;
    Impl.MetricLogging -> MetricLogging;

    //components new TimerMilliC() as DetectTimer;
    //Impl.DetectTimer -> DetectTimer;

    components new TimerMilliC() as OnTimerC;
    components new TimerMilliC() as OffTimerC;
    Impl.OffTimer -> OffTimerC;
    Impl.OnTimer -> OnTimerC;
}
