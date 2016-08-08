#include "MetricLogging.h"

configuration PrintfMetricLoggingP
{
	provides interface MetricLogging;
}
implementation
{
	components PrintfMetricLoggingImplP as App;

	MetricLogging = App;

#ifdef USE_SERIAL_PRINTF
	// Serial / Printf
	components PrintfC;
	components SerialStartC;

	// Time
	components LocalTimeMilliC;
	
	App.LocalTime -> LocalTimeMilliC;
#endif
}
