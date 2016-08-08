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

#ifndef TOSSIM
	components LocalTimeMilliC;
	
	App.LocalTime -> LocalTimeMilliC;
#endif

#if defined(TOSSIM) || defined(USE_SERIAL_PRINTF)
	components PrintfMetricLoggingP;

	App.MetricLogging -> PrintfMetricLoggingP;

#elif defined(USE_SERIAL_MESSAGES)
	components SerialMetricLoggingP;

	App.MetricLogging -> SerialMetricLoggingP;

#else
#	error "No known combination to wire up metric logging"
#endif

	// Radio Control
	components ActiveMessageC;

	App.RadioControl -> ActiveMessageC;


	// Timers
	components new TimerMilliC() as BroadcastNormalTimer;
	components new TimerMilliC() as AwaySenderTimer;
	components new TimerMilliC() as BeaconSenderTimer;
	components new TimerMilliC() as DummyNormalSenderTimer;

	App.BroadcastNormalTimer -> BroadcastNormalTimer;
	App.AwaySenderTimer -> AwaySenderTimer;
	App.BeaconSenderTimer -> BeaconSenderTimer;
	App.DummyNormalSenderTimer -> DummyNormalSenderTimer;


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
		new AMSenderC(FAKE_CHANNEL) as FakeSender,
		new AMReceiverC(FAKE_CHANNEL) as FakeReceiver;

	App.FakeSend -> FakeSender;
	App.FakeReceive -> FakeReceiver;

	components
		new AMSenderC(DUMMYNORMAL_CHANNEL) as DummyNormalSender,
		new AMReceiverC(DUMMYNORMAL_CHANNEL) as DummyNormalReceiver;

	App.DummyNormalSend -> DummyNormalSender;
	App.DummyNormalReceive -> DummyNormalReceiver;

	components
		new AMSenderC(BEACON_CHANNEL) as BeaconSender,
		new AMReceiverC(BEACON_CHANNEL) as BeaconReceiver;

	App.BeaconSend -> BeaconSender;
	App.BeaconReceive -> BeaconReceiver;

	components FakeMessageGeneratorP;
	App.FakeMessageGenerator -> FakeMessageGeneratorP;

	components ObjectDetectorP;
	App.ObjectDetector -> ObjectDetectorP;

	components
		new SequenceNumbersP(SLP_MAX_NUM_SOURCES) as NormalSeqNos;
	App.NormalSeqNos -> NormalSeqNos;

	components
		new DictionaryP(am_addr_t, uint16_t, SLP_MAX_NUM_SOURCES) as SourceDistances,
		new DictionaryP(am_addr_t, uint16_t, SLP_MAX_NUM_SOURCES) as SinkSourceDistances;
	App.SourceDistances -> SourceDistances;
	App.SinkSourceDistances -> SinkSourceDistances;
}
