#include "MetricLogging.h"

configuration PrintfMetricLoggingP
{
	provides interface MetricLogging;

	uses interface MessageType;
}
implementation
{
	components PrintfMetricLoggingImplP as App;

	MetricLogging = App;

	App.MessageType = MessageType;

#ifdef USE_SERIAL_PRINTF
	components SerialStartC;

#if defined(SERIAL_PRINTF_UNBUFFERED)
	components SerialPrintfC;
#elif defined(SERIAL_PRINTF_BUFFERED)
	components PrintfC;
#elif defined(SERIAL_PRINTF_UART)
	components UartPrintfC;
#else
#	error "Serial Printf needs to be buffered or unbuffered, but is neither."
#endif
#endif

	// Time
	components LocalTimeMilliC;
	App.LocalTime -> LocalTimeMilliC;

	components Base16C;
	App.Encode -> Base16C;
}
