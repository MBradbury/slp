configuration NodeRebootFaultModelP
{
    provides interface FaultModel;

    uses interface MetricLogging;
    uses interface FaultModelTypes;
}
implementation
{
    components NodeRebootFaultModelImplP as ProvidedFaultModel;

    FaultModel = ProvidedFaultModel;
    ProvidedFaultModel.FaultModelTypes = FaultModelTypes;
    ProvidedFaultModel.MetricLogging = MetricLogging;

    components HardwareC;
    ProvidedFaultModel.Hardware -> HardwareC;
}
