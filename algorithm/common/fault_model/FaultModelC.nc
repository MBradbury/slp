
generic configuration FaultModelC(uint8_t maximum_fault_point_types)
{
    provides interface FaultModel;

    uses interface MetricLogging;
}
implementation
{
    components new FaultModelTypesP(maximum_fault_point_types);

#if defined(SLP_NO_FAULT_MODEL)
#   warning "Using NoFaultModelP as the fault model"

    components NoFaultModelP as ProvidedFaultModel;

#elif defined(SLP_TOSSIM_FAULT_MODEL)
#   if defined(TOSSIM)
#      warning "Using TossimFaultModelP as the fault model"

    components TossimFaultModelP as ProvidedFaultModel;
#   else
#       error "Cannot use SLP_TOSSIM_FAULT_MODEL if not using TOSSIM"
#   endif

#elif defined(SLP_NESC_FAULT_MODEL)
#   warning "Using " SLP_NESC_FAULT_MODEL " as the fault model"

    components SLP_NESC_FAULT_MODEL as ProvidedFaultModel;

#else
#   error "Not sure which fault model to use"
#endif

#warning "*** FaultModelC is present"

    FaultModel = ProvidedFaultModel;
    ProvidedFaultModel.FaultModelTypes -> FaultModelTypesP;
    FaultModelTypesP.MetricLogging = MetricLogging;
    ProvidedFaultModel.MetricLogging = MetricLogging;

    components MainC;
    MainC.SoftwareInit -> FaultModelTypesP;
}
