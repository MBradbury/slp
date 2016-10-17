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
	App.AMPacket -> ActiveMessageC;

	// Timers

	// Object Detector - For Source movement
	components ObjectDetectorP;
	App.ObjectDetector -> ObjectDetectorP;
	ObjectDetectorP.NodeType -> NodeTypeP;

	components SourcePeriodModelP;
	App.SourcePeriodModel -> SourcePeriodModelP;

	components
		new SequenceNumbersP(SLP_MAX_NUM_SOURCES) as NormalSeqNos;
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