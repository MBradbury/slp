#include "MetricLogging.h"

#ifndef MESSAGE_QUEUE_SIZE
#	define MESSAGE_QUEUE_SIZE 24
#endif

#ifndef USE_SERIAL_MESSAGES
#	error "Must only use MetricLoggingP when USE_SERIAL_MESSAGES is defined"
#endif

configuration SerialMetricLoggingP
{
	provides interface MetricLogging;
}
implementation
{
	components SerialMetricLoggingImplP as App;

	MetricLogging = App;

	components SerialStartC;

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

	components
		new SerialAMSenderC(AM_METRIC_RECEIVE_MSG) as MetricReceiveSender,
		new SerialAMSenderC(AM_METRIC_BCAST_MSG) as MetricBcastSender,
		new SerialAMSenderC(AM_METRIC_DELIVER_MSG) as MetricDeliverSender,
		new SerialAMSenderC(AM_ATTACKER_RECEIVE_MSG) as AttackerReceiveSender,
		new SerialAMSenderC(AM_METRIC_NODE_CHANGE_MSG) as MetricNodeChangeSender;

	App.MetricReceiveSend -> MetricReceiveSender;
	App.MetricBcastSend -> MetricBcastSender;
	App.MetricDeliverSend -> MetricDeliverSender;
	App.AttackerReceiveSend -> AttackerReceiveSender;
	App.MetricNodeChangeSend -> MetricNodeChangeSender;
}
