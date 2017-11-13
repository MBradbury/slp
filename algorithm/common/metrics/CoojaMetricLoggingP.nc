#include "MetricLogging.h"

#ifndef CYCLEACCURATE_COOJA
#   error "Must only be used by Cooja"
#endif

configuration CoojaMetricLoggingP
{
    provides interface MetricLogging;

    uses interface MessageType;
}
implementation
{
    components PrintfMetricLoggingImplP as App;

    MetricLogging = App;

    App.MessageType = MessageType;

    components CoojaPrintfC;

    // Time
    components LocalTimeMilliC;
    App.LocalTime -> LocalTimeMilliC;
}
