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


	// Timers
	components new TimerMilliC() as BroadcastNormalTimer;

	App.BroadcastNormalTimer -> BroadcastNormalTimer;


	// Networking
	components
		new AMSenderC(NORMAL_CHANNEL) as NormalSender,
		new AMReceiverC(NORMAL_CHANNEL) as NormalReceiver,
		new AMSnooperC(NORMAL_CHANNEL) as NormalSnooper;

	App.Packet -> NormalSender; // TODO: is this right?
	App.AMPacket -> NormalSender; // TODO: is this right?
	
	App.NormalSend -> NormalSender;
	App.NormalReceive -> NormalReceiver;
	App.NormalSnoop -> NormalSnooper;


	// Object Detector - For Source movement
	components ObjectDetectorP;
	App.ObjectDetector -> ObjectDetectorP;

	// SourcePeriodModel - for source periods
	components SourcePeriodModelP;
	App.SourcePeriodModel -> SourcePeriodModelP;

    // Random
    components RandomC;
    App.Random -> RandomC;

    components
		new SequenceNumbersP(SLP_MAX_NUM_SOURCES) as NormalSeqNos;
	App.NormalSeqNos -> NormalSeqNos;
}
