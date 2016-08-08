#include "MetricLogging.h"

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

	components SerialActiveMessageC;

	App.Packet -> SerialActiveMessageC;
	//App.AMPacket -> SerialActiveMessageC;

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
