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

	components new NodeTypeP(6);
	App.NodeType -> NodeTypeP;
	NodeTypeP.MetricLogging -> MetricLogging;

	components new MessageTypeP(6);
	App.MessageType -> MessageTypeP;
	MessageTypeP.MetricLogging -> MetricLogging;

	MetricLogging.MessageType -> MessageTypeP;

	// Radio Control
	components ActiveMessageC;

	App.RadioControl -> ActiveMessageC;


	// Timers

	// Networking

	// Object Detector - For Source movement
	components ObjectDetectorP;
	App.ObjectDetector -> ObjectDetectorP;
	ObjectDetectorP.NodeType -> NodeTypeP;

	components SourcePeriodModelP;
	App.SourcePeriodModel -> SourcePeriodModelP;
}
