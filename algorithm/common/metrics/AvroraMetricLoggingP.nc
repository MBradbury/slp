#include "MetricLogging.h"

#ifndef CYCLEACCURATE_AVRORA
#	error "Must only be used by Avrora"
#endif

configuration AvroraMetricLoggingP
{
	provides interface MetricLogging;

	uses interface MessageType;
}
implementation
{
	components AvroraMetricLoggingImplP as App;

	MetricLogging = App;

	App.MessageType = MessageType;

	components AvroraPrintfC;
	App.AvroraPrintf -> AvroraPrintfC;

	// Time
	components LocalTimeMilliC;
	App.LocalTime -> LocalTimeMilliC;
}
