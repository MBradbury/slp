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
	components DelayedBootEventMainP as MainC;
	components LedsWhenGuiC as LedsC;

	App.Boot -> MainC;
	App.Leds -> LedsC;

	components MetricLoggingP as MetricLogging;
	App.MetricLogging -> MetricLogging;
	
	components MetricHelpersP as MetricHelpers;
	App.MetricHelpers -> MetricHelpers;

	components new NodeTypeC(3);
	App.NodeType -> NodeTypeC;
	NodeTypeC.MetricLogging -> MetricLogging;

	components new MessageTypeC(1);
	App.MessageType -> MessageTypeC;
	MessageTypeC.MetricLogging -> MetricLogging;

	MetricLogging.MessageType -> MessageTypeC;

	// Radio Control
	components ActiveMessageC;

	App.RadioControl -> ActiveMessageC;

	// Timers


	// Networking
	components
		new AMSenderC(NORMAL_CHANNEL) as NormalSender,
		new AMReceiverC(NORMAL_CHANNEL) as NormalReceiver;
	
	App.Packet -> NormalSender; // TODO: is this right?
	App.AMPacket -> NormalSender; // TODO: is this right?
	
	App.NormalSend -> NormalSender;
	App.NormalReceive -> NormalReceiver;


	// Object Detector - For Source movement
	components ObjectDetectorP;
	App.ObjectDetector -> ObjectDetectorP;
	ObjectDetectorP.NodeType -> NodeTypeC;

	components SourcePeriodModelP;
	App.SourcePeriodModel -> SourcePeriodModelP;

	components
		new SequenceNumbersC(SLP_MAX_NUM_SOURCES) as NormalSeqNos;
	App.NormalSeqNos -> NormalSeqNos;
}
