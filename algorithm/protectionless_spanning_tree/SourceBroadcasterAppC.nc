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

	components new NodeTypeC(6);
	App.NodeType -> NodeTypeC;
	NodeTypeC.MetricLogging -> MetricLogging;

	components new MessageTypeC(6);
	App.MessageType -> MessageTypeC;
	MessageTypeC.MetricLogging -> MetricLogging;

	MetricLogging.MessageType -> MessageTypeC;

	// Radio Control
	components ActiveMessageC;

	App.RadioControl -> ActiveMessageC;
	App.Packet -> ActiveMessageC;
	App.AMPacket -> ActiveMessageC;

	// Timers

	// Object Detector - For Source movement
	components ObjectDetectorP;
	App.ObjectDetector -> ObjectDetectorP;
	ObjectDetectorP.NodeType -> NodeTypeC;

	components SourcePeriodModelP;
	App.SourcePeriodModel -> SourcePeriodModelP;

	components
		new SequenceNumbersC(SLP_MAX_NUM_SOURCES) as NormalSeqNos;
	App.NormalSeqNos -> NormalSeqNos;

	components SpanningTreeC;
	App.RoutingControl -> SpanningTreeC;
	App.RootControl -> SpanningTreeC;

	SpanningTreeC.MetricLogging -> MetricLogging;

	// Networking
	App.NormalSend -> SpanningTreeC.Send[NORMAL_CHANNEL];
	App.NormalReceive -> SpanningTreeC.Receive[NORMAL_CHANNEL];
	App.NormalSnoop -> SpanningTreeC.Snoop[NORMAL_CHANNEL];
	App.NormalIntercept -> SpanningTreeC.Intercept[NORMAL_CHANNEL];
}
