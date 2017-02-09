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
    components DelayedBootEventMainP as MainC;
    components LedsWhenGuiC as LedsC;
    
    App.Boot -> MainC;
    App.Leds -> LedsC;

    components MetricLoggingP as MetricLogging;

    App.MetricLogging -> MetricLogging;

    components new NodeTypeP(6);
    App.NodeType -> NodeTypeP;
    NodeTypeP.MetricLogging -> MetricLogging;

    components new MessageTypeP(2);
    App.MessageType -> MessageTypeP;
    MessageTypeP.MetricLogging -> MetricLogging;

    MetricLogging.MessageType -> MessageTypeP;

    // Radio Control
    components ActiveMessageC;

    App.RadioControl -> ActiveMessageC;


    // Timers
    components
        new TimerMilliC() as BroadcastTimer;

    App.BroadcastTimer -> BroadcastTimer;


    // Networking
    components
        new AMSenderC(NORMAL_CHANNEL) as NormalSender,
        new AMReceiverC(NORMAL_CHANNEL) as NormalReceiver;
    
    App.Packet -> NormalSender; // TODO: is this right?
    App.AMPacket -> NormalSender; // TODO: is this right?
    
    App.NormalSend -> NormalSender;
    App.NormalReceive -> NormalReceiver;

    components
        new AMSenderC(DUMMY_NORMAL_CHANNEL) as DummyNormalSender,
        new AMReceiverC(DUMMY_NORMAL_CHANNEL) as DummyNormalReceiver;

    App.DummyNormalSend -> DummyNormalSender;
    App.DummyNormalReceive -> DummyNormalReceiver;

    // Message Queue
    components
        new PoolC(NormalMessage, MESSAGE_QUEUE_SIZE) as MessagePool,
        new QueueC(NormalMessage*, MESSAGE_QUEUE_SIZE) as MessageQueue;

    App.MessagePool -> MessagePool;
    App.MessageQueue -> MessageQueue;


    // Object Detector - For Source movement
    components ObjectDetectorP;
    App.ObjectDetector -> ObjectDetectorP;
    ObjectDetectorP.NodeType -> NodeTypeP;

    components SourcePeriodModelP;
    App.SourcePeriodModel -> SourcePeriodModelP;

    components
        new SequenceNumbersP(SLP_MAX_NUM_SOURCES) as NormalSeqNos;
    App.NormalSeqNos -> NormalSeqNos;
}
