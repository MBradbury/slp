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

	components new MessageTypeP(6);
	App.MessageType -> MessageTypeP;
	MessageTypeP.MetricLogging -> MetricLogging;

#if defined(USE_SERIAL_MESSAGES)
	MetricLogging.MessageType -> MessageTypeP;
#endif

	// Radio Control
	components ActiveMessageC;

	App.RadioControl -> ActiveMessageC;


	// Timers
	components new TimerMilliC() as BroadcastNormalTimer;

	App.BroadcastNormalTimer -> BroadcastNormalTimer;


	// Networking
	components
		new AMSenderC(NORMAL_CHANNEL) as NormalSender,
		new AMReceiverC(NORMAL_CHANNEL) as NormalReceiver,
		new AMSnooperC(NORMAL_CHANNEL) as NormalSnooper;

	App.Packet -> NormalSender; // TODO: is this right?
	App.AMPacket -> NormalSender; // TODO: is this right?
	
	App.NormalSend -> NormalSender;
	App.NormalReceive -> NormalReceiver;
	App.NormalSnoop -> NormalSnooper;


	// Object Detector - For Source movement
	components ObjectDetectorP;
	App.ObjectDetector -> ObjectDetectorP;
	ObjectDetectorP.NodeType -> NodeTypeP;

	// SourcePeriodModel - for source periods
	components SourcePeriodModelP;
	App.SourcePeriodModel -> SourcePeriodModelP;

    // Random
    components RandomC;
    App.Random -> RandomC;

    components
		new SequenceNumbersP(SLP_MAX_NUM_SOURCES) as NormalSeqNos;
	App.NormalSeqNos -> NormalSeqNos;
}
