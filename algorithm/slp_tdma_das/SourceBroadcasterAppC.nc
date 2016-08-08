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
    components PrintfMetricLoggingP;

    App.MetricLogging -> PrintfMetricLoggingP;

#elif defined(USE_SERIAL_MESSAGES)
    components SerialMetricLoggingP;

    App.MetricLogging -> SerialMetricLoggingP;

#else
#   error "No known combination to wire up metric logging"
#endif

    // Radio Control
    components ActiveMessageC;

    App.RadioControl -> ActiveMessageC;

    // Timers
    components
        new TimerMilliC() as DissemTimer,
        new TimerMilliC() as DissemTimerSender,
        new TimerMilliC() as PreSlotTimer,
        new TimerMilliC() as SlotTimer,
        new TimerMilliC() as PostSlotTimer;

    App.DissemTimer -> DissemTimer;
    App.DissemTimerSender -> DissemTimerSender;
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

    components
        new AMSenderC(SEARCH_CHANNEL) as SearchSender,
        new AMReceiverC(SEARCH_CHANNEL) as SearchReceiver;

    App.SearchSend -> SearchSender;
    App.SearchReceive -> SearchReceiver;

    components
        new AMSenderC(CHANGE_CHANNEL) as ChangeSender,
        new AMReceiverC(CHANGE_CHANNEL) as ChangeReceiver;

    App.ChangeSend -> ChangeSender;
    App.ChangeReceive ->ChangeReceiver;

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
