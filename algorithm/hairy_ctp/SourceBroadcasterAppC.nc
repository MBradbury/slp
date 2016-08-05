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

#ifdef USE_SERIAL_PRINTF
	components SerialPrintfC;
#endif

	// Radio Control
	components ActiveMessageC;

	App.RadioControl -> ActiveMessageC;
	App.AMPacket -> ActiveMessageC;

	// Timers
	components new TimerMilliC() as BroadcastBeaconTimer;
	components new TimerMilliC() as FakeWalkTimer;
	components new TimerMilliC() as FakeSendTimer;
	components new TimerMilliC() as EtxTimer;

	App.BroadcastBeaconTimer -> BroadcastBeaconTimer;
	App.FakeWalkTimer -> FakeWalkTimer;
	App.FakeSendTimer -> FakeSendTimer;
	App.EtxTimer -> EtxTimer;


	// Object Detector - For Source movement
	components ObjectDetectorP;
	App.ObjectDetector -> ObjectDetectorP;

	components SourcePeriodModelP;
	App.SourcePeriodModel -> SourcePeriodModelP;

	components
		new SequenceNumbersP(SLP_MAX_NUM_SOURCES) as NormalSeqNos;
	App.NormalSeqNos -> NormalSeqNos;

	components CollectionC;
	App.RoutingControl -> CollectionC;
	App.RootControl -> CollectionC;
	//App.CollectionPacket -> CollectionC;
	App.CtpInfo -> CollectionC;
	//App.CtpCongestion -> CollectionC;

	CollectionC.CollectionDebug -> App;

	components new CollectionSenderC(NORMAL_CHANNEL);

	// Networking
	App.NormalSend -> CollectionSenderC;
	App.NormalReceive -> CollectionC.Receive[NORMAL_CHANNEL];
	App.NormalSnoop -> CollectionC.Snoop[NORMAL_CHANNEL];
	App.NormalIntercept -> CollectionC.Intercept[NORMAL_CHANNEL];

	components
		new AMSenderC(CHOOSE_CHANNEL) as ChooseSender,
		new AMReceiverC(CHOOSE_CHANNEL) as ChooseReceiver,
		new AMSnooperC(CHOOSE_CHANNEL) as ChooseSnooper;

	App.ChooseSend -> ChooseSender;
	App.ChooseReceive -> ChooseReceiver;
	App.ChooseSnoop -> ChooseSnooper;

	components
		new AMSenderC(FAKE_CHANNEL) as FakeSender,
		new AMReceiverC(FAKE_CHANNEL) as FakeReceiver,
		new AMSnooperC(FAKE_CHANNEL) as FakeSnooper;

	App.FakeSend -> FakeSender;
	App.FakeReceive -> FakeReceiver;
	App.FakeSnoop -> FakeSnooper;

	components
		new AMSenderC(BEACON_CHANNEL) as BeaconSender,
		new AMReceiverC(BEACON_CHANNEL) as BeaconReceiver;

	App.BeaconSend -> BeaconSender;
	App.BeaconReceive -> BeaconReceiver;


	components
		new DictionaryP(am_addr_t, uint16_t, SLP_MAX_NUM_SOURCES) as Sources;
	App.Sources -> Sources;


	components
		new DictionaryP(am_addr_t, uint16_t, SLP_MAX_1_HOP_NEIGHBOURHOOD) as NeighboursMinSourceDistance;
	App.NeighboursMinSourceDistance -> NeighboursMinSourceDistance;
}
