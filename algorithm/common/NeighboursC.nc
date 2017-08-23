#include "NeighboursRtxInfo.h"

generic configuration NeighboursC(
	typedef Info, uint8_t MAX_SIZE,
	typedef NBeaconMessage, am_id_t BEACON_CHANNEL,
	typedef NPollMessage, am_id_t POLL_CHANNEL)
{
	provides interface Neighbours<Info, NBeaconMessage, NPollMessage>;

	uses interface MetricLogging;
	uses interface MetricHelpers;
	uses interface NodeType;
}
implementation
{
	components new NeighboursImplC(Info, MAX_SIZE, NBeaconMessage, NPollMessage) as App;

	Neighbours = App;

	App.MetricLogging = MetricLogging;
	App.MetricHelpers = MetricHelpers;
	App.NodeType = NodeType;

	components LedsWhenGuiC;
	App.Leds -> LedsWhenGuiC;

	components RandomC;
	App.Random -> RandomC;

#ifdef METRIC_LOGGING_NEEDS_LOCALTIME
	components LocalTimeMilliC;
	App.LocalTime -> LocalTimeMilliC;
#endif

	components new DictionaryC(am_addr_t, Info, MAX_SIZE) as NeighbourDict;
	App.NeighbourDict -> NeighbourDict;

	components new DictionaryC(am_addr_t, NeighboursRtxInfo, MAX_SIZE) as NeighbourRtxDict;
	App.NeighbourRtxDict -> NeighbourRtxDict;

    components CommonCompareC;
    NeighbourDict.Compare -> CommonCompareC;
    NeighbourRtxDict.Compare -> CommonCompareC;


	components new TimerMilliC() as BeaconSenderTimer;
	App.BeaconSenderTimer -> BeaconSenderTimer;

	components
        new AMSenderC(BEACON_CHANNEL) as BeaconSender,
        new AMReceiverC(BEACON_CHANNEL) as BeaconReceiver;

    App.BeaconSend -> BeaconSender;
    App.BeaconReceive -> BeaconReceiver;

    components
        new AMSenderC(POLL_CHANNEL) as PollSender,
        new AMReceiverC(POLL_CHANNEL) as PollReceiver;

    App.PollSend -> PollSender;
    App.PollReceive -> PollReceiver;

    App.AMPacket -> BeaconSender;
}
