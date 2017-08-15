#include "MetricLogging.h"

configuration MetricHelpersP
{
	provides interface MetricHelpers;
}
implementation
{
	components MetricHelpersImplP as App;

	MetricHelpers = App;

#ifdef TOSSIM
	components TossimActiveMessageC;
	App.TossimPacket -> TossimActiveMessageC;
#else
	components CC2420ActiveMessageC;
	App.CC2420Packet -> CC2420ActiveMessageC;
#endif
}
