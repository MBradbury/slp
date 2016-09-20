#include "SpanningTree.h"

configuration SpanningTreeC {
  provides {
    interface StdControl; // To stop / start the tree
    interface RootControl; // To control who is a point on the tree 

    /*interface Send[uint8_t client];
    interface Receive[collection_id_t id];
    interface Receive as Snoop[collection_id_t];
    interface Intercept[collection_id_t id];

    interface Packet;*/
  }

  uses {
    interface NodeType;
    interface MetricLogging;
  }
}

implementation {
  components SpanningTreeSetupP as Setup;
  components SpanningTreeRoutingP as Routing;

  // Provides forwarding
  StdControl = Setup;
  RootControl = Routing;

  // Uses forwarding
  Setup.NodeType = NodeType;
  Setup.MetricLogging = MetricLogging;

  components RandomC;
  Setup.Random -> RandomC;

  components ActiveMessageC;

  /*Send = Setup;
  Receive = Setup.Receive;
  Snoop = Setup.Snoop;
  Intercept = Setup;
  Packet = Setup;*/

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
    new TimerMilliC() as ConnectTimer;

  Setup.ConnectTimer -> ConnectTimer;

  components
    new DictionaryP(am_addr_t, uint16_t, SLP_MAX_1_HOP_NEIGHBOURHOOD) as NeighbourRanks;

  Setup.PDict -> NeighbourRanks;

  components
    new SetP(am_addr_t, SLP_MAX_1_HOP_NEIGHBOURHOOD) as Connections;

  Setup.Connections -> Connections;
}
