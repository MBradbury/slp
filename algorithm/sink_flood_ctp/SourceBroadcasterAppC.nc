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
	
	App.Boot -> MainC;
	App.Leds -> LedsC;

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
	App.AMPacket -> ActiveMessageC;

	// Timers
	components new TimerMilliC() as BroadcastFakeTimer;

	App.BroadcastFakeTimer -> BroadcastFakeTimer;


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
	//App.CtpInfo -> CollectionC;
	//App.CtpCongestion -> CollectionC;

	CollectionC.CollectionDebug -> App;

	components new CollectionSenderC(NORMAL_CHANNEL);

	// Networking
	App.NormalSend -> CollectionSenderC;
	App.NormalReceive -> CollectionC.Receive[NORMAL_CHANNEL];
	App.NormalSnoop -> CollectionC.Snoop[NORMAL_CHANNEL];
	App.NormalIntercept -> CollectionC.Intercept[NORMAL_CHANNEL];

	components
		new AMSenderC(FAKE_CHANNEL) as FakeSender,
		new AMReceiverC(FAKE_CHANNEL) as FakeReceiver;

	App.FakeSend -> FakeSender;
	App.FakeReceive -> FakeReceiver;
}
