#include "MetricLogging.h"

configuration MetricLoggingP
{
	provides interface MetricLogging;

	uses interface MessageType;
}
implementation
{
#if defined(TOSSIM) || defined(USE_SERIAL_PRINTF)
	components PrintfMetricLoggingP as ProvidedMetricLogging;
#elif defined(USE_SERIAL_MESSAGES)
	components SerialMetricLoggingP as ProvidedMetricLogging;
#elif defined(NO_SERIAL_OUTPUT)
	components NoMetricLoggingP as ProvidedMetricLogging;
#elif defined(CYCLEACCURATE_AVRORA) && defined(AVRORA_OUTPUT)
	components AvroraMetricLoggingP as ProvidedMetricLogging;
#elif defined(CYCLEACCURATE_COOJA) && defined(COOJA_OUTPUT)
    components CoojaMetricLoggingP as ProvidedMetricLogging;
#else
#	error "No known combination to wire up metric logging"
#endif

	MetricLogging = ProvidedMetricLogging;

	ProvidedMetricLogging.MessageType = MessageType;
}
