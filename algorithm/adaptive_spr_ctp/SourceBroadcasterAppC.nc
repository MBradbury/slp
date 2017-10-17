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
	App.AMPacket -> ActiveMessageC;
	App.Packet -> ActiveMessageC;


	// Timers
	components new TimerMilliC() as BroadcastNormalTimer;
	components new TimerMilliC() as AwaySenderTimer;
	components new TimerMilliC() as ChooseSenderTimer;
	components new TimerMilliC() as BeaconSenderTimer;

	App.BroadcastNormalTimer -> BroadcastNormalTimer;
	App.AwaySenderTimer -> AwaySenderTimer;
	App.ChooseSenderTimer -> ChooseSenderTimer;
	App.BeaconSenderTimer -> BeaconSenderTimer;

	// Networking
	components
		new AMSenderC(AWAY_CHANNEL) as AwaySender,
		new AMReceiverC(AWAY_CHANNEL) as AwayReceiver;

	App.AwaySend -> AwaySender;
	App.AwayReceive -> AwayReceiver;

	components
		new AMSenderC(CHOOSE_CHANNEL) as ChooseSender,
		new AMReceiverC(CHOOSE_CHANNEL) as ChooseReceiver,
		new AMSnooperC(CHOOSE_CHANNEL) as ChooseSnooper;

	App.ChooseSend -> ChooseSender;
	App.ChooseReceive -> ChooseReceiver;
	App.ChooseSnoop -> ChooseSnooper;

	components
		new AMSenderC(FAKE_CHANNEL) as FakeSender,
		new AMReceiverC(FAKE_CHANNEL) as FakeReceiver;

	App.FakeSend -> FakeSender;
	App.FakeReceive -> FakeReceiver;

	components
		new AMSenderC(BEACON_CHANNEL) as BeaconSender,
		new AMReceiverC(BEACON_CHANNEL) as BeaconReceiver;

	App.BeaconSend -> BeaconSender;
	App.BeaconReceive -> BeaconReceiver;

	components
		new AMSenderC(NOTIFY_CHANNEL) as NotifySender,
		new AMReceiverC(NOTIFY_CHANNEL) as NotifyReceiver;

	App.NotifySend -> NotifySender;
	App.NotifyReceive -> NotifyReceiver;


	components FakeMessageGeneratorP;
	App.FakeMessageGenerator -> FakeMessageGeneratorP;
	FakeMessageGeneratorP.Packet -> ActiveMessageC;
	FakeMessageGeneratorP.MetricLogging -> MetricLogging;
	FakeMessageGeneratorP.MetricHelpers -> MetricHelpers;

	components ObjectDetectorP;
	App.ObjectDetector -> ObjectDetectorP;
	ObjectDetectorP.NodeType -> NodeTypeC;

	components
		new SequenceNumbersC(SLP_MAX_NUM_SOURCES) as NormalSeqNos;
	App.NormalSeqNos -> NormalSeqNos;

	components CollectionC;
	App.RoutingControl -> CollectionC;
	App.RootControl -> CollectionC;
	//App.CollectionPacket -> CollectionC;
	//App.CtpInfo -> CollectionC;
	//App.CtpCongestion -> CollectionC;

	components new CollectionSenderC(NORMAL_CHANNEL);

	App.NormalSend -> CollectionSenderC;
	App.NormalReceive -> CollectionC.Receive[NORMAL_CHANNEL];
	App.NormalSnoop -> CollectionC.Snoop[NORMAL_CHANNEL];
	App.NormalIntercept -> CollectionC.Intercept[NORMAL_CHANNEL];


	components CTPMetricsP;
	CTPMetricsP.MetricLogging -> MetricLogging;
	CTPMetricsP.MetricHelpers -> MetricHelpers;
	CTPMetricsP.CtpInfo -> CollectionC;
	CollectionC.CollectionDebug -> CTPMetricsP;
}
