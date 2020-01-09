
module NoFaultModelP
{
    provides interface FaultModel;

    uses interface MetricLogging;
    uses interface FaultModelTypes;
}
implementation
{
    command bool FaultModel.register_pair(uint8_t ident, const char* name)
    {
        return call FaultModelTypes.register_pair(ident, name);
    }

    command uint8_t FaultModel.from_string(const char* name)
    {
        return call FaultModelTypes.from_string(name);
    }

    command const char* FaultModel.to_string(uint8_t ident)
    {
        return call FaultModelTypes.to_string(ident);
    }

    command void FaultModel.fault_point(uint8_t ident)
    {
    }
}
