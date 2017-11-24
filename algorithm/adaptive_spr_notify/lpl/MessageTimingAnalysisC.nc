
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
}