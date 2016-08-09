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
    components RandomC;
    components LocalTimeMilliC;
    
    App.Boot -> MainC;
    App.Leds -> LedsC;
    App.Random -> RandomC;
    App.LocalTime -> LocalTimeMilliC;

#if defined(TOSSIM) || defined(USE_SERIAL_PRINTF)
    components PrintfMetricLoggingP as MetricLogging;
#elif defined(USE_SERIAL_MESSAGES)
    components SerialMetricLoggingP as MetricLogging;
#else
#   error "No known combination to wire up metric logging"
#endif

    App.MetricLogging -> MetricLogging;

    components new NodeTypeP(6);
    App.NodeType -> NodeTypeP;
    NodeTypeP.MetricLogging -> MetricLogging;

    // Radio Control
    components ActiveMessageC;

    App.RadioControl -> ActiveMessageC;

    // Timers
    components
        /*new TimerMilliC() as BroadcastTimer,*/
        new TimerMilliC() as DissemTimer,
        new TimerMilliC() as DissemTimerSender,
        new TimerMilliC() as EnqueueNormalTimer,
        new TimerMilliC() as PreSlotTimer,
        new TimerMilliC() as SlotTimer,
        new TimerMilliC() as PostSlotTimer;

    /*App.BroadcastTimer -> BroadcastTimer;*/
    App.DissemTimer -> DissemTimer;
    App.DissemTimerSender -> DissemTimerSender;
    /*App.EnqueueNormalTimer -> EnqueueNormalTimer;*/
    App.PreSlotTimer -> PreSlotTimer;
    App.SlotTimer -> SlotTimer;
    App.PostSlotTimer -> PostSlotTimer;

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

    components SourcePeriodModelP;
    App.SourcePeriodModel -> SourcePeriodModelP;

    components
        new SequenceNumbersP(SLP_MAX_NUM_SOURCES) as NormalSeqNos;
    App.NormalSeqNos -> NormalSeqNos;
}
