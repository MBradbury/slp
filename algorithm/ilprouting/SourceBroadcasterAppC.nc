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

    components new NodeTypeC(3);
    App.NodeType -> NodeTypeC;
    NodeTypeC.MetricLogging -> MetricLogging;

    components new MessageTypeC(4);
    App.MessageType -> MessageTypeC;
    MessageTypeC.MetricLogging -> MetricLogging;

    MetricLogging.MessageType -> MessageTypeC;

    // Radio Control
    components ActiveMessageC;

    App.RadioControl -> ActiveMessageC;


    // Timers
    components new TimerMilliC() as ConsiderTimer;
    components new TimerMilliC() as AwaySenderTimer;

    App.ConsiderTimer -> ConsiderTimer;
    App.AwaySenderTimer -> AwaySenderTimer;

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

    components new NeighboursC(
        ni_container_t, SLP_MAX_1_HOP_NEIGHBOURHOOD,
        BeaconMessage, BEACON_CHANNEL,
        PollMessage, POLL_CHANNEL);
    App.Neighbours -> NeighboursC;

    NeighboursC.MetricLogging -> MetricLogging;
    NeighboursC.NodeType -> NodeTypeC;



    // Object Detector - For Source movement
    components ObjectDetectorP;
    App.ObjectDetector -> ObjectDetectorP;
    ObjectDetectorP.NodeType -> NodeTypeC;

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
        new DictionaryC(SeqNoWithAddr, message_queue_info_t*, SLP_SEND_QUEUE_SIZE) as MessageQueueP;

    App.MessagePool -> MessagePoolP;
    App.MessageQueue -> MessageQueueP;

    MessageQueueP.Compare -> App;

    // Time
    components LocalTimeMilliC;
    
    App.LocalTime -> LocalTimeMilliC;
}
