generic configuration FaultModelC(uint8_t maximum_fault_point_types)
{
    provides interface FaultModel;

    uses interface MetricLogging;
}
implementation
{
#if defined(TOSSIM)
    components new TossimFaultModelP(maximum_fault_point_types) as ProvidedFaultModel;
#else
#   warning "Fault model not available for current environment"
    components new NoFaultModelP(maximum_fault_point_types) as ProvidedFaultModel;
#endif

    FaultModel = ProvidedFaultModel;
    ProvidedFaultModel.MetricLogging = MetricLogging;

    components MainC;
    MainC.SoftwareInit -> ProvidedFaultModel;
}
