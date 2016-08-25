#include "Constants.h"

#include <Timer.h>

configuration SourceBroadcasterAppC
{
}

implementation
{
	// The application
	components SourceBroadcasterC as App;

	// Low levels events such as boot and LED control
	components MainC;
	components LedsC;
	
	App.Boot -> MainC;
	App.Leds -> LedsC;

#ifndef TOSSIM
	components LocalTimeMilliC;
	
	App.LocalTime -> LocalTimeMilliC;
#endif

#if defined(TOSSIM) || defined(USE_SERIAL_PRINTF)
	components PrintfMetricLoggingP as MetricLogging;
#elif defined(USE_SERIAL_MESSAGES)
	components SerialMetricLoggingP as MetricLogging;
#else
#	error "No known combination to wire up metric logging"
#endif

	App.MetricLogging -> MetricLogging;

	components new NodeTypeP(6);
	App.NodeType -> NodeTypeP;
	NodeTypeP.MetricLogging -> MetricLogging;

#if defined(USE_SERIAL_MESSAGES)
	MetricLogging.NodeType -> NodeTypeP;
#endif

	// Radio Control
	components ActiveMessageC;

	App.RadioControl -> ActiveMessageC;


	// Timers
	components new TimerMilliC() as BroadcastNormalTimer;

	App.BroadcastNormalTimer -> BroadcastNormalTimer;

	components new TimerMilliC() as AwaySenderTimer;

	App.AwaySenderTimer -> AwaySenderTimer;

	components new TimerMilliC() as BeaconSenderTimer;

	App.BeaconSenderTimer -> BeaconSenderTimer;


	// Networking
	components
		new AMSenderC(NORMAL_CHANNEL) as NormalSender,
		new AMReceiverC(NORMAL_CHANNEL) as NormalReceiver,
		new AMSnooperC(NORMAL_CHANNEL) as NormalSnooper;

	components
		new AMSenderC(AWAY_CHANNEL) as AwaySender,
		new AMReceiverC(AWAY_CHANNEL) as AwayReceiver;

	components
		new AMSenderC(BEACON_CHANNEL) as BeaconSender,
		new AMReceiverC(BEACON_CHANNEL) as BeaconReceiver;
	
	App.Packet -> AwaySender; // TODO: is this right?
	App.AMPacket -> AwaySender; // TODO: is this right?
	
	App.NormalSend -> NormalSender;
	App.NormalReceive -> NormalReceiver;
	App.NormalSnoop -> NormalSnooper;

	App.AwaySend -> AwaySender;
	App.AwayReceive -> AwayReceiver;

	App.BeaconSend -> BeaconSender;
	App.BeaconReceive -> BeaconReceiver;


	// Object Detector - For Source movement
	components ObjectDetectorP;
	App.ObjectDetector -> ObjectDetectorP;
	ObjectDetectorP.NodeType -> NodeTypeP;

	components SourcePeriodModelP;
	App.SourcePeriodModel -> SourcePeriodModelP;

	components
		new SequenceNumbersP(SLP_MAX_NUM_SOURCES) as NormalSeqNos,
		new SequenceNumbersP(SLP_MAX_NUM_SINKS) as AwaySeqNos;
	App.NormalSeqNos -> NormalSeqNos;
	App.AwaySeqNos -> AwaySeqNos;

	// Random
    components RandomC;
    App.Random -> RandomC;
}
