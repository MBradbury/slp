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


	// Timers

	// Networking

	// Object Detector - For Source movement
	components ObjectDetectorP;
	App.ObjectDetector -> ObjectDetectorP;
	ObjectDetectorP.NodeType -> NodeTypeC;

	components SourcePeriodModelP;
	App.SourcePeriodModel -> SourcePeriodModelP;
}
