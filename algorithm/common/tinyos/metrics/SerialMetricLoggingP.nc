#include "MetricLogging.h"

#ifndef MESSAGE_QUEUE_SIZE
#	define MESSAGE_QUEUE_SIZE 64
#endif

#ifndef USE_SERIAL_MESSAGES
#	error "Must only use MetricLoggingP when USE_SERIAL_MESSAGES is defined"
#endif

configuration SerialMetricLoggingP
{
	provides interface MetricLogging;

	uses interface MessageType;
}
implementation
{
	components SerialMetricLoggingImplP as App;

	MetricLogging = App;

	App.MessageType = MessageType;

	components SerialStartC;

	components MainC;
	MainC.SoftwareInit -> App;

	components LocalTimeMilliC;
	App.LocalTime -> LocalTimeMilliC;

	// Message Queue
    components
        new PoolC(message_t, MESSAGE_QUEUE_SIZE) as MessagePool,
        new QueueC(message_t*, MESSAGE_QUEUE_SIZE) as MessageQueue;

    App.MessagePool -> MessagePool;
    App.MessageQueue -> MessageQueue;

    // Serial messages
	components SerialActiveMessageC;

	App.Packet -> SerialActiveMessageC;
	App.AMPacket -> SerialActiveMessageC;
	App.SerialSend -> SerialActiveMessageC;
}
