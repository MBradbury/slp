#include "NeighboursRtxInfo.h"

generic configuration NeighboursC(
	typedef Info, uint8_t MAX_SIZE,
	typedef NBeaconMessage, am_id_t BEACON_CHANNEL,
	typedef NPollMessage, am_id_t POLL_CHANNEL)
{
	provides interface Neighbours<Info, NBeaconMessage, NPollMessage>;

	uses interface MetricLogging;
	uses interface NodeType;
}
implementation
{
	components new NeighboursImplC(Info, MAX_SIZE, NBeaconMessage, NPollMessage) as App;

	Neighbours = App;

	App.MetricLogging = MetricLogging;
	App.NodeType = NodeType;

	components LedsC;
	App.Leds -> LedsC;

	components RandomC;
	App.Random -> RandomC;

	components new DictionaryP(am_addr_t, Info, MAX_SIZE) as NeighbourDict;
	App.NeighbourDict -> NeighbourDict;

	components new DictionaryP(am_addr_t, NeighboursRtxInfo, MAX_SIZE) as NeighbourRtxDict;
	App.NeighbourRtxDict -> NeighbourRtxDict;

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
