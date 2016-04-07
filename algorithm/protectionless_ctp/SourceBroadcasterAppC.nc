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

#ifdef USE_SERIAL_PRINTF
	components SerialPrintfC;
#endif

	// Radio Control
	components ActiveMessageC;

	App.RadioControl -> ActiveMessageC;
	App.AMPacket -> ActiveMessageC;

	// Timers
	components new TimerMilliC() as BroadcastNormalTimer;

	App.BroadcastNormalTimer -> BroadcastNormalTimer;


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

	CollectionC.CollectionDebug -> App;

	components new CollectionSenderC(NORMAL_CHANNEL);

	// Networking
	App.NormalSend -> CollectionSenderC;
	App.NormalReceive -> CollectionC.Receive[NORMAL_CHANNEL];
	App.NormalSnoop -> CollectionC.Snoop[NORMAL_CHANNEL];
	App.NormalIntercept -> CollectionC.Intercept[NORMAL_CHANNEL];

	App.Packet -> CollectionC;
	App.RootControl -> CollectionC;
	//App.CollectionPacket -> CollectionC;
	//App.CtpInfo -> CollectionC;
	//App.CtpCongestion -> CollectionC;
}
