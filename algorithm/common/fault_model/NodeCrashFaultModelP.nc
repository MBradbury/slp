configuration NodeCrashFaultModelP
{
    provides interface FaultModel;

    uses interface MetricLogging;
    uses interface FaultModelTypes;
}
implementation
{
    components NodeCrashFaultModelImplP as ProvidedFaultModel;

    FaultModel = ProvidedFaultModel;
    ProvidedFaultModel.FaultModelTypes = FaultModelTypes;
    ProvidedFaultModel.MetricLogging = MetricLogging;

    components McuSleepC;
    ProvidedFaultModel.McuSleep = McuSleepC;
}
