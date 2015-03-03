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


	// Radio Control
	components ActiveMessageC;
	components TossimActiveMessageC;

	App.RadioControl -> ActiveMessageC;
	App.TossimPacket -> TossimActiveMessageC;


	// Timers
	components new TimerMilliC() as BroadcastNormalTimer;

	App.BroadcastNormalTimer -> BroadcastNormalTimer;

	components new TimerMilliC() as AwaySenderTimer;

	App.AwaySenderTimer -> AwaySenderTimer;

	// LocalTime
	components LocalTimeMilliC;
	App.LocalTime -> LocalTimeMilliC;


	// Networking
	components
		new AMSenderC(NORMAL_CHANNEL) as NormalSender,
		new AMReceiverC(NORMAL_CHANNEL) as NormalReceiver;

	components
		new AMSenderC(AWAY_CHANNEL) as AwaySender,
		new AMReceiverC(AWAY_CHANNEL) as AwayReceiver;


	// Object Detector - For Source movement
	components ObjectDetectorP;

	App.ObjectDetector -> ObjectDetectorP;

    //Random
    components RandomC;
	
	App.Packet -> NormalSender; // TODO: is this right?
	App.AMPacket -> NormalSender; // TODO: is this right?
	
	App.NormalSend -> NormalSender;
	App.NormalReceive -> NormalReceiver;

	App.AwaySend -> AwaySender;
	App.AwayReceive -> AwayReceiver;
        
    App.Random->RandomC;
}
