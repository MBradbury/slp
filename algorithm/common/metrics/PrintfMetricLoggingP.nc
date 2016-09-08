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

#if defined(SERIAL_PRINTF_UNBUFFERED)
	components SerialPrintfC;
#elif defined(SERIAL_PRINTF_BUFFERED)
	// Serial / Printf
	components PrintfC;
	components SerialStartC;
#else
#	error "Serial Printf needs to be buffered or unbuffered, but is neither."
#endif

	// Time
	components LocalTimeMilliC;
	
	App.LocalTime -> LocalTimeMilliC;
#endif
}
