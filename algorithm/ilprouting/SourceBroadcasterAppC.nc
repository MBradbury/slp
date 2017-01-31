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
    components RandomC;
    
    App.Boot -> MainC;
    App.Leds -> LedsC;
    App.Random -> RandomC;

    components MetricLoggingP as MetricLogging;

    App.MetricLogging -> MetricLogging;

    components new NodeTypeP(3);
    App.NodeType -> NodeTypeP;
    NodeTypeP.MetricLogging -> MetricLogging;

    components new MessageTypeP(3);
    App.MessageType -> MessageTypeP;
    MessageTypeP.MetricLogging -> MetricLogging;

    MetricLogging.MessageType -> MessageTypeP;

    // Radio Control
    components ActiveMessageC;

    App.RadioControl -> ActiveMessageC;


    // Timers
    components new TimerMilliC() as ConsiderTimer;
    components new TimerMilliC() as AwaySenderTimer;
    components new TimerMilliC() as BeaconSenderTimer;
    components new TimerMilliC() as ObjectDetectorStartTimer;

    App.ConsiderTimer -> ConsiderTimer;
    App.AwaySenderTimer -> AwaySenderTimer;
    App.BeaconSenderTimer -> BeaconSenderTimer;
    App.ObjectDetectorStartTimer -> ObjectDetectorStartTimer;

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
    App.NormalPacketAcknowledgements -> NormalSender.Acks;

    components
        new AMSenderC(AWAY_CHANNEL) as AwaySender,
        new AMReceiverC(AWAY_CHANNEL) as AwayReceiver;

    App.AwaySend -> AwaySender;
    App.AwayReceive -> AwayReceiver;

    components
        new AMSenderC(BEACON_CHANNEL) as BeaconSender,
        new AMReceiverC(BEACON_CHANNEL) as BeaconReceiver;

    App.BeaconSend -> BeaconSender;
    App.BeaconReceive -> BeaconReceiver;


    // Object Detector - For Source movement
    components ObjectDetectorP;
    App.ObjectDetector -> ObjectDetectorP;
    ObjectDetectorP.NodeType -> NodeTypeP;

    components SourcePeriodModelP;
    App.SourcePeriodModel -> SourcePeriodModelP;

    components
        new CircularBufferC(SeqNoWithFlag, SLP_MAX_NUM_SOURCES * SLP_SEND_QUEUE_SIZE) as LruNormalSeqNos;
    App.LruNormalSeqNos -> LruNormalSeqNos;

    // Pool / Queue
    STATIC_ASSERT_MSG(SLP_SEND_QUEUE_SIZE > 0, SLP_SEND_QUEUE_SIZE_must_be_gt_0);
    STATIC_ASSERT_MSG(SLP_SEND_QUEUE_SIZE < 255, SLP_SEND_QUEUE_SIZE_must_be_lt_255);

    components
        new PoolC(message_queue_info_t, SLP_SEND_QUEUE_SIZE) as MessagePoolP,
        new DictionaryP(SeqNoWithAddr, message_queue_info_t*, SLP_SEND_QUEUE_SIZE) as MessageQueueP;

    App.MessagePool -> MessagePoolP;
    App.MessageQueue -> MessageQueueP;

    // Time
    components LocalTimeMilliC;
    
    App.LocalTime -> LocalTimeMilliC;
}
