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
    components CrcC;
    components RandomC;
    components LocalTimeMilliC;
    
    App.Boot -> MainC;
    App.Leds -> LedsC;
    App.Crc -> CrcC;
    App.Random -> RandomC;
    App.LocalTime -> LocalTimeMilliC;

    components MetricLoggingP as MetricLogging;

    App.MetricLogging -> MetricLogging;

    components new NodeTypeC(6);
    App.NodeType -> NodeTypeC;
    NodeTypeC.MetricLogging -> MetricLogging;

    components MetricHelpersP as MetricHelpers;
    App.MetricHelpers -> MetricHelpers;

    components new MessageTypeC(6);
    App.MessageType -> MessageTypeC;
    MessageTypeC.MetricLogging -> MetricLogging;

    MetricLogging.MessageType -> MessageTypeC;

    components TDMAP;

    TDMAP.NodeType -> NodeTypeC;
    App.TDMA -> TDMAP;
    TDMAP.MetricLogging -> MetricLogging;

    // Radio Control
    components ActiveMessageC;

    App.RadioControl -> ActiveMessageC;

    // Timers
    components
        new TimerMilliC() as DissemTimerSender;

    App.DissemTimerSender -> DissemTimerSender;

    // Networking
    components
        new AMSenderC(NORMAL_CHANNEL) as NormalSender,
        new AMReceiverC(NORMAL_CHANNEL) as NormalReceiver;
    
    App.Packet -> NormalSender; // TODO: is this right?
    App.AMPacket -> NormalSender; // TODO: is this right?
    
    App.NormalSend -> NormalSender;
    App.NormalReceive -> NormalReceiver;

    /*components*/
        /*new AMSenderC(BEACON_CHANNEL) as BeaconSender,*/
        /*new AMReceiverC(BEACON_CHANNEL) as BeaconReceiver;*/

    /*App.BeaconSend -> BeaconSender;*/
    /*App.BeaconReceive -> BeaconReceiver;*/

    components
        new AMSenderC(DISSEM_CHANNEL) as DissemSender,
        new AMReceiverC(DISSEM_CHANNEL) as DissemReceiver;

    App.DissemSend -> DissemSender;
    App.DissemReceive -> DissemReceiver;

    components
        new AMSenderC(EMPTYNORMAL_CHANNEL) as EmptyNormalSender,
        new AMReceiverC(EMPTYNORMAL_CHANNEL) as EmptyNormalReceiver;

    App.EmptyNormalSend -> EmptyNormalSender;
    App.EmptyNormalReceive -> EmptyNormalReceiver;

    /*components*/
        /*new AMSenderC(COLLISION_CHANNEL) as CollisionSender,*/
        /*new AMReceiverC(COLLISION_CHANNEL) as CollisionReceiver;*/

    /*App.CollisionSend -> CollisionSender;*/
    /*App.CollisionReceive ->CollisionReceiver;*/

    // Message Queue
    components
        new PoolC(NormalMessage, MESSAGE_QUEUE_SIZE) as MessagePool,
        new QueueC(NormalMessage*, MESSAGE_QUEUE_SIZE) as MessageQueue;

    App.MessagePool -> MessagePool;
    App.MessageQueue -> MessageQueue;


    // Object Detector - For Source movement
    components ObjectDetectorP;
    App.ObjectDetector -> ObjectDetectorP;
    ObjectDetectorP.NodeType -> NodeTypeC;

    components SourcePeriodModelP;
    App.SourcePeriodModel -> SourcePeriodModelP;

    components
        new SequenceNumbersC(SLP_MAX_NUM_SOURCES) as NormalSeqNos;
    App.NormalSeqNos -> NormalSeqNos;

    components
        new SequenceNumbersC(SLP_MAX_2_HOP_NEIGHBOURHOOD) as EmptyNormalSeqNos;
    App.EmptyNormalSeqNos -> EmptyNormalSeqNos;
}
