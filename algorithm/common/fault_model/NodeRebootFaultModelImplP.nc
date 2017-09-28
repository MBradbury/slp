
#include "MetricLogging.h"

module NodeRebootFaultModelImplP
{
    provides interface FaultModel;

    uses interface MetricLogging;
    uses interface FaultModelTypes;

    interface Hardware;
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
        call Hardware.reboot();
    }

    event void RadioControl.startDone(error_t error)
    {
    }

    event void RadioControl.stopDone(error_t error)
    {
    }
}
