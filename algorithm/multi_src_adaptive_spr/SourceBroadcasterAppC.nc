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
	components RandomC;
	
	App.Boot -> MainC;
	App.Leds -> LedsC;
	App.Random -> RandomC;

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
	components new TimerMilliC() as AwaySenderTimer;
	components new TimerMilliC() as BeaconSenderTimer;

	App.BroadcastNormalTimer -> BroadcastNormalTimer;
	App.AwaySenderTimer -> AwaySenderTimer;
	App.BeaconSenderTimer -> BeaconSenderTimer;

	// Networking
	components
		new AMSenderC(NORMAL_CHANNEL) as NormalSender,
		new AMReceiverC(NORMAL_CHANNEL) as NormalReceiver;
	
	App.Packet -> NormalSender; // TODO: is this right?
	App.AMPacket -> NormalSender; // TODO: is this right?
	
	App.NormalSend -> NormalSender;
	App.NormalReceive -> NormalReceiver;

	components
		new AMSenderC(AWAY_CHANNEL) as AwaySender,
		new AMReceiverC(AWAY_CHANNEL) as AwayReceiver;

	App.AwaySend -> AwaySender;
	App.AwayReceive -> AwayReceiver;

	components
		new AMSenderC(CHOOSE_CHANNEL) as ChooseSender,
		new AMReceiverC(CHOOSE_CHANNEL) as ChooseReceiver;

	App.ChooseSend -> ChooseSender;
	App.ChooseReceive -> ChooseReceiver;

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

	components FakeMessageGeneratorP;
	App.FakeMessageGenerator -> FakeMessageGeneratorP;
	FakeMessageGeneratorP.Packet -> ActiveMessageC;
	FakeMessageGeneratorP.MetricLogging -> MetricLogging;

	components ObjectDetectorP;
	App.ObjectDetector -> ObjectDetectorP;
	ObjectDetectorP.NodeType -> NodeTypeP;

	components
		new SequenceNumbersP(SLP_MAX_NUM_SOURCES) as NormalSeqNos;
	App.NormalSeqNos -> NormalSeqNos;

	components
		new DictionaryP(am_addr_t, uint16_t, SLP_MAX_NUM_SOURCES) as SourceDistances,
		new DictionaryP(am_addr_t, uint16_t, SLP_MAX_NUM_SOURCES) as SinkSourceDistances;
	App.SourceDistances -> SourceDistances;
	App.SinkSourceDistances -> SinkSourceDistances;
}
