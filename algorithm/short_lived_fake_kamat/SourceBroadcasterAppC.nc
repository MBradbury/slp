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
	components RandomC;
	
	App.Boot -> MainC;
	App.Leds -> LedsC;
	App.Random -> RandomC;

	components MetricLoggingP as MetricLogging;

	App.MetricLogging -> MetricLogging;

	components new NodeTypeP(4);
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
	components new TimerMilliC() as BroadcastNormalTimer;
	App.BroadcastNormalTimer -> BroadcastNormalTimer;

	components new TimerMilliC() as BroadcastFakeTimer;
	App.BroadcastFakeTimer -> BroadcastFakeTimer;


	// Networking
	components
		new AMSenderC(NORMAL_CHANNEL) as NormalSender,
		new AMReceiverC(NORMAL_CHANNEL) as NormalReceiver;
	
	App.Packet -> NormalSender; // TODO: is this right?
	App.AMPacket -> NormalSender; // TODO: is this right?
	
	App.NormalSend -> NormalSender;
	App.NormalReceive -> NormalReceiver;

	components
		new AMSenderC(FAKE_CHANNEL) as FakeSender,
		new AMReceiverC(FAKE_CHANNEL) as FakeReceiver;

	App.FakeSend -> FakeSender;
	App.FakeReceive -> FakeReceiver;

	components ObjectDetectorP;
	App.ObjectDetector -> ObjectDetectorP;
	ObjectDetectorP.NodeType -> NodeTypeP;

	components
		new SequenceNumbersP(SLP_MAX_NUM_SOURCES) as NormalSeqNos;
	App.NormalSeqNos -> NormalSeqNos;
}
