
generic configuration MessageTimingAnalysisC()
{
    provides interface MessageTimingAnalysis;
}
implementation
{
    components new MessageTimingAnalysisP();
    MessageTimingAnalysisP.MessageTimingAnalysis = MessageTimingAnalysis;

    components MainC;
    MessageTimingAnalysisP.Init <- MainC.SoftwareInit;

    components MetricLoggingP as MetricLogging;
    MessageTimingAnalysisP.MetricLogging -> MetricLogging;

    components LocalTimeMilliC;
    MessageTimingAnalysisP.LocalTime -> LocalTimeMilliC;

    components new TimerMilliC() as DetectTimer;
    MessageTimingAnalysisP.DetectTimer -> DetectTimer;

    components new TimerMilliC() as OnTimerC;
    components new TimerMilliC() as OffTimerC;
    MessageTimingAnalysisP.OffTimer -> OffTimerC;
    MessageTimingAnalysisP.OnTimer -> OnTimerC;
}
