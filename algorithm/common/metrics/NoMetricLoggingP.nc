#include "MetricLogging.h"

configuration NoMetricLoggingP
{
	provides interface MetricLogging;

	uses interface MessageType;
}
implementation
{
	components NoMetricLoggingImplP as App;

	MetricLogging = App;

	App.MessageType = MessageType;
}
