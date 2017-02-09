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
    components RandomC;
    components LocalTimeMilliC;
    
    App.Boot -> MainC;
    App.Leds -> LedsC;
    App.Random -> RandomC;
    App.LocalTime -> LocalTimeMilliC;

    components MetricLoggingP as MetricLogging;

    App.MetricLogging -> MetricLogging;

    components new NodeTypeP(6);
    App.NodeType -> NodeTypeP;
    NodeTypeP.MetricLogging -> MetricLogging;

    components new MessageTypeP(6);
    App.MessageType -> MessageTypeP;
    MessageTypeP.MetricLogging -> MetricLogging;

    MetricLogging.MessageType -> MessageTypeP;

    components TDMAP;

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
    App.DissemReceive ->DissemReceiver;

    components
        new AMSenderC(SEARCH_CHANNEL) as SearchSender,
        new AMReceiverC(SEARCH_CHANNEL) as SearchReceiver;

    App.SearchSend -> SearchSender;
    App.SearchReceive -> SearchReceiver;

    components
        new AMSenderC(CHANGE_CHANNEL) as ChangeSender,
        new AMReceiverC(CHANGE_CHANNEL) as ChangeReceiver;

    App.ChangeSend -> ChangeSender;
    App.ChangeReceive -> ChangeReceiver;

    components
        new AMSenderC(EMPTYNORMAL_CHANNEL) as EmptyNormalSender,
        new AMReceiverC(EMPTYNORMAL_CHANNEL) as EmptyNormalReceiver;

    App.EmptyNormalSend -> EmptyNormalSender;
    App.EmptyNormalReceive -> EmptyNormalReceiver;

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
