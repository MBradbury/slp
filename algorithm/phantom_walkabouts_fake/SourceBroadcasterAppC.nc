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
	components new TimerMilliC() as BroadcastNormalTimer;

	App.BroadcastNormalTimer -> BroadcastNormalTimer;

	components new TimerMilliC() as AwaySenderTimer;

	App.AwaySenderTimer -> AwaySenderTimer;

	components new TimerMilliC() as DelayBLSenderTimer;

	App.DelayBLSenderTimer -> DelayBLSenderTimer;

	components new TimerMilliC() as DelayBRSenderTimer;

	App.DelayBRSenderTimer -> DelayBRSenderTimer;

	components new TimerMilliC() as BeaconSenderTimer;

	App.BeaconSenderTimer -> BeaconSenderTimer;

	components new TimerMilliC() as BroadcastFakeTimer;

	App.BroadcastFakeTimer -> BroadcastFakeTimer;


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

	components
		new AMSenderC(FAKE_CHANNEL) as FakeSender,
		new AMReceiverC(FAKE_CHANNEL) as FakeReceiver;

	App.FakeSend -> FakeSender;
	App.FakeReceive -> FakeReceiver;

	App.Packet -> AwaySender; // TODO: is this right?
	App.AMPacket -> AwaySender; // TODO: is this right?
	
	App.NormalSend -> NormalSender;
	App.NormalReceive -> NormalReceiver;
	App.NormalSnoop -> NormalSnooper;

	App.AwaySend -> AwaySender;
	App.AwayReceive -> AwayReceiver;

	App.BeaconSend -> BeaconSender;
	App.BeaconReceive -> BeaconReceiver;

	components FakeMessageGeneratorP;
	App.FakeMessageGenerator -> FakeMessageGeneratorP;
	FakeMessageGeneratorP.Packet -> ActiveMessageC;
	FakeMessageGeneratorP.MetricLogging -> MetricLogging;

	// Object Detector - For Source movement
	components ObjectDetectorP;
	App.ObjectDetector -> ObjectDetectorP;
	ObjectDetectorP.NodeType -> NodeTypeP;


	// SourcePeriodModel - for source periods
	components SourcePeriodModelP;
	App.SourcePeriodModel -> SourcePeriodModelP;

	components
		new SequenceNumbersP(SLP_MAX_NUM_SOURCES) as NormalSeqNos,
		new SequenceNumbersP(SLP_MAX_NUM_AWAY_MESSAGES) as AwaySeqNos;
	App.NormalSeqNos -> NormalSeqNos;
	App.AwaySeqNos -> AwaySeqNos;
}
