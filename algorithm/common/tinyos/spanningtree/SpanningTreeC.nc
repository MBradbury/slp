#include "SpanningTree.h"

configuration SpanningTreeC {
  provides {
    interface StdControl; // To stop / start the tree
    interface RootControl; // To control who is a point on the tree 

    interface Send[uint8_t client];
    interface Receive[uint8_t id];
    interface Receive as Snoop[uint8_t id];
    interface Intercept[uint8_t id];

    interface Packet;

    interface LinkEstimator;
  }

  uses {
    interface MetricLogging;
  }
}

implementation {
  components SpanningTreeSetupP as Setup;
  components SpanningTreeRoutingP as Routing;
  components SpanningTreeInfoP as Info;

  // Provides forwarding
  StdControl = Setup;
  RootControl = Info;

  Send = Routing;
  Receive = Routing.Receive;
  Snoop = Routing.Snoop;
  Intercept = Routing;
  Packet = Routing;

  // Uses forwarding
  Setup.MetricLogging = MetricLogging;
  Routing.MetricLogging = MetricLogging;

  // Info wiring

  Setup.Info -> Info;
  Setup.RootControl -> Info;

  Routing.Info -> Info;
  Routing.RootControl -> Info;

  // Setup and Routing wiring

  components RandomC;
  Setup.Random -> RandomC;
  Routing.Random -> RandomC;

  components LinkEstimatorP;
  Setup.LinkEstimator -> LinkEstimatorP;
  Routing.LinkEstimator -> LinkEstimatorP;

  StdControl = LinkEstimatorP;
  LinkEstimator = LinkEstimatorP;

  components ActiveMessageC;

  // Common

  components
    new AMSenderC(AM_SPANNING_TREE_ROUTE) as RoutingSender,
    new AMReceiverC(AM_SPANNING_TREE_ROUTE) as RoutingReceiver,
    new AMSnooperC(AM_SPANNING_TREE_ROUTE) as RoutingSnooper;

  // Setup wring

  //Setup.SetupSend -> SetupSender;
  //Setup.SetupReceive -> SetupReceiver;

  Setup.SetupSend -> LinkEstimatorP.Send;
  Setup.SetupReceive -> LinkEstimatorP.Receive;

  Setup.AMPacket -> ActiveMessageC;

  components
    new AMSenderC(AM_SPANNING_TREE_CONNECT) as ConnectSender,
    new AMReceiverC(AM_SPANNING_TREE_CONNECT) as ConnectReceiver,
    new AMSnooperC(AM_SPANNING_TREE_CONNECT) as ConnectSnooper;

  Setup.ConnectSend -> ConnectSender;
  Setup.ConnectReceive -> ConnectReceiver;
  Setup.ConnectSnoop -> ConnectSnooper;

  Setup.RoutingSend -> RoutingSender;

  Setup.PacketAcknowledgements -> ConnectSender.Acks;

  components
    new TimerMilliC() as SetupTimer,
    new TimerMilliC() as ConnectTimer;

  Setup.SetupTimer -> SetupTimer;
  Setup.ConnectTimer -> ConnectTimer;

  components CommonCompareC;
  components
    new DictionaryC(am_addr_t, uint16_t, SLP_MAX_1_HOP_NEIGHBOURHOOD) as NeighbourRootDistances;

  Setup.NeighbourRootDistances -> NeighbourRootDistances;
  NeighbourRootDistances.Compare -> CommonCompareC;

  components
    new SetC(am_addr_t, SLP_MAX_1_HOP_NEIGHBOURHOOD) as Connections;

  Setup.Connections -> Connections;
  Connections.Compare -> CommonCompareC;

  // Routing wiring

  Routing.SubSend -> RoutingSender;
  Routing.SubReceive -> RoutingReceiver;
  Routing.SubSnoop -> RoutingSnooper;

  Routing.SubPacket -> RoutingSender;
  Routing.SubAMPacket -> RoutingSender;
  Routing.PacketAcknowledgements -> RoutingSender.Acks;

  components
    new TimerMilliC() as RetransmitTimer;

  Routing.RetransmitTimer -> RetransmitTimer;

  components
    new PoolC(message_t, SLP_SEND_QUEUE_SIZE) as MessagePoolP,
    new PoolC(send_queue_item_t, SLP_SEND_QUEUE_SIZE) as QueuePoolP,
    new QueueC(send_queue_item_t*, SLP_SEND_QUEUE_SIZE) as SendQueueP;

  Routing.MessagePool -> MessagePoolP;
  Routing.QueuePool -> QueuePoolP;
  Routing.SendQueue -> SendQueueP;

  components
    new CircularBufferC(spanning_tree_data_header_t, SLP_SEND_QUEUE_SIZE) as SentCache;

  Routing.SentCache -> SentCache;
  SentCache.Compare -> Routing.SpanningTreeHeaderCompare;

  // LinkEstimator wiring

  LinkEstimatorP.Random -> RandomC;

  components
    new AMSenderC(AM_SPANNING_TREE_SETUP) as SetupSender,
    new AMReceiverC(AM_SPANNING_TREE_SETUP) as SetupReceiver;

  LinkEstimatorP.AMSend -> SetupSender;
  LinkEstimatorP.SubReceive -> SetupReceiver;
  LinkEstimatorP.SubPacket -> SetupSender;
  LinkEstimatorP.SubAMPacket -> SetupSender;
}
