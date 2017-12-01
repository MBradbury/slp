
#include "MetricLogging.h"

module NodeCrashFaultModelImplP
{
    provides interface FaultModel;

    provides interface Init;

    uses interface MetricLogging;
    uses interface FaultModelTypes;

    uses interface SplitControl as RadioControl;
}
implementation
{
    bool crashed;

    command error_t Init.init()
    {
        crashed = FALSE;

        return SUCCESS;
    }

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
        crashed = TRUE;

        call RadioControl.stop();
    }

    event void RadioControl.startDone(error_t error)
    {
        if (crashed)
        {
            call RadioControl.stop();
        }
    }

    event void RadioControl.stopDone(error_t error)
    {
    }
}
