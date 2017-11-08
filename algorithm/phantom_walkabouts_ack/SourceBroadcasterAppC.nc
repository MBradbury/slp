#include "Constants.h"
#include "MessageQueueInfo.h"
#include "SeqNoWithFlag.h"

#include "pp.h"

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
	components CrcC;
	
	App.Boot -> MainC;
	App.Leds -> LedsC;
	App.Crc -> CrcC;

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

	components new TimerMilliC() as ConsiderTimer;
	App.ConsiderTimer -> ConsiderTimer;

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

	App.Packet -> AwaySender; // TODO: is this right?
	App.AMPacket -> AwaySender; // TODO: is this right?
	
	App.NormalSend -> NormalSender;
	App.NormalReceive -> NormalReceiver;
	App.NormalSnoop -> NormalSnooper;
	App.NormalPacketAcknowledgements -> NormalSender.Acks;

	App.AwaySend -> AwaySender;
	App.AwayReceive -> AwayReceiver;

	App.BeaconSend -> BeaconSender;
	App.BeaconReceive -> BeaconReceiver;

	// Object Detector - For Source movement
	components ObjectDetectorP;
	App.ObjectDetector -> ObjectDetectorP;
	ObjectDetectorP.NodeType -> NodeTypeC;

	components
		new SequenceNumbersC(SLP_MAX_NUM_SOURCES) as NormalSeqNos,
		new SequenceNumbersC(SLP_MAX_NUM_AWAY_MESSAGES) as AwaySeqNos;
	App.NormalSeqNos -> NormalSeqNos;
	App.AwaySeqNos -> AwaySeqNos;

	components
		new CircularBufferC(SeqNoWithAddr, SLP_MAX_NUM_SOURCES * SLP_SEND_QUEUE_SIZE) as LruNormalSeqNos;
	App.LruNormalSeqNos -> LruNormalSeqNos;
	LruNormalSeqNos.Compare -> App;

	// Pool / Queue
	STATIC_ASSERT_MSG(SLP_SEND_QUEUE_SIZE > 0, SLP_SEND_QUEUE_SIZE_must_be_gt_0);
	STATIC_ASSERT_MSG(SLP_SEND_QUEUE_SIZE < 255, SLP_SEND_QUEUE_SIZE_must_be_lt_255);

	components
		new PoolC(message_queue_info_t, SLP_SEND_QUEUE_SIZE) as MessagePoolP,
		new DictionaryC(SeqNoWithAddr, message_queue_info_t*, SLP_SEND_QUEUE_SIZE) as MessageQueueP;

	App.MessagePool -> MessagePoolP;
	App.MessageQueue -> MessageQueueP;

	MessageQueueP.Compare -> App;
 
    // Random
    components RandomC;
    App.Random -> RandomC;

    App.SeedInit -> RandomC.SeedInit;

    // Time
	components LocalTimeMilliC;
	App.LocalTime -> LocalTimeMilliC;
}
