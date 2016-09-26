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
  }

  uses {
    interface NodeType;
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
  Setup.NodeType = NodeType;
  Setup.MetricLogging = MetricLogging;

  // Info wiring

  Setup.Info -> Info;
  Routing.Info -> Info;
  Routing.RootControl -> Info;

  // Setup and Routing wiring

  components RandomC;
  Setup.Random -> RandomC;
  Routing.Random -> RandomC;

  // Setup wring
  components
    new AMSenderC(AM_SPANNING_TREE_SETUP) as SetupSender,
    new AMReceiverC(AM_SPANNING_TREE_SETUP) as SetupReceiver;

  Setup.SetupSend -> SetupSender;
  Setup.SetupReceive -> SetupReceiver;

  components
    new AMSenderC(AM_SPANNING_TREE_CONNECT) as ConnectSender,
    new AMReceiverC(AM_SPANNING_TREE_CONNECT) as ConnectReceiver;

  Setup.ConnectSend -> ConnectSender;
  Setup.ConnectReceive -> ConnectReceiver;

  components
    new TimerMilliC() as SetupTimer,
    new TimerMilliC() as ConnectTimer;

  Setup.SetupTimer -> SetupTimer;
  Setup.ConnectTimer -> ConnectTimer;

  components
    new DictionaryP(am_addr_t, uint16_t, SLP_MAX_1_HOP_NEIGHBOURHOOD) as NeighbourRanks;

  Setup.PDict -> NeighbourRanks;

  components
    new SetP(am_addr_t, SLP_MAX_1_HOP_NEIGHBOURHOOD) as Connections;

  Setup.Connections -> Connections;

  // Routing wiring

  components
    new AMSenderC(AM_SPANNING_TREE_ROUTE) as RoutingSender,
    new AMReceiverC(AM_SPANNING_TREE_ROUTE) as RoutingReceiver,
    new AMSnooperC(AM_SPANNING_TREE_ROUTE) as RoutingSnooper;

  Routing.SubSend -> RoutingSender;
  Routing.SubReceive -> RoutingReceiver;
  Routing.SubSnoop -> RoutingSnooper;

  Routing.SubPacket -> RoutingSender;
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
}
