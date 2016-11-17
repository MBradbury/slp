#include "Constants.h"
#include "MessageQueueInfo.h"

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

    components new MessageTypeP(6);
    App.MessageType -> MessageTypeP;
    MessageTypeP.MetricLogging -> MetricLogging;

#if defined(USE_SERIAL_MESSAGES)
    MetricLogging.MessageType -> MessageTypeP;
#endif

    // Radio Control
    components ActiveMessageC;

    App.RadioControl -> ActiveMessageC;


    // Timers
    components new TimerMilliC() as ConsiderTimer;

    App.ConsiderTimer -> ConsiderTimer;

    // Networking
    components
        new AMSenderC(NORMAL_CHANNEL) as NormalSender,
        new AMReceiverC(NORMAL_CHANNEL) as NormalReceiver;
    
    App.Packet -> NormalSender; // TODO: is this right?
    App.AMPacket -> NormalSender; // TODO: is this right?
    
    App.NormalSend -> NormalSender;
    App.NormalReceive -> NormalReceiver;


    // Object Detector - For Source movement
    components ObjectDetectorP;
    App.ObjectDetector -> ObjectDetectorP;
    ObjectDetectorP.NodeType -> NodeTypeP;

    components SourcePeriodModelP;
    App.SourcePeriodModel -> SourcePeriodModelP;

    components
        new SequenceNumbersP(SLP_MAX_NUM_SOURCES) as NormalSeqNos;
    App.NormalSeqNos -> NormalSeqNos;

    // Pool / Queue
    components
        new PoolC(message_queue_info_t, SLP_SEND_QUEUE_SIZE) as MessagePoolP,
        new QueueC(message_queue_info_t*, SLP_SEND_QUEUE_SIZE) as MessageQueueP;

    App.MessagePool -> MessagePoolP;
    App.MessageQueue -> MessageQueueP;

    // Time
    components LocalTimeMilliC;
    
    App.LocalTime -> LocalTimeMilliC;
}
