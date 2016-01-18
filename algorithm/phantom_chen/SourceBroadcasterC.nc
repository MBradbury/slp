#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "NormalMessage.h"

#include <Timer.h>
#include <TinyError.h>

#include <assert.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)

//define as global, as making it work for multiple sources.
uint16_t messageNo = 0;

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;

	uses interface Timer<TMilli> as BroadcastNormalTimer;

	uses interface Packet;
	uses interface AMPacket;

	uses interface SplitControl as RadioControl;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;
	uses interface Receive as NormalSnoop;

	uses interface SourcePeriodModel;
	uses interface ObjectDetector;

	uses interface SequenceNumbers as NormalSeqNos;

	uses interface Random;
}

implementation 
{
	typedef enum
	{
		SourceNode, SinkNode, NormalNode
	} NodeType;

	NodeType type = NormalNode;

	typedef enum
	{
		UnknownSet = 0, CloserSet = (1 << 0), FurtherSet = (1 << 1)
	} SetType;

	const char* type_to_string()
	{
		switch (type)
		{
			case SourceNode:      return "SourceNode";
			case SinkNode:        return "SinkNode  ";
			case NormalNode:      return "NormalNode";
			default:              return "<unknown> ";
		}
	}

	bool busy = FALSE;
	message_t packet;

	uint32_t extra_to_send = 0;

	uint32_t get_source_period()
	{
		assert(type == SourceNode);
		return call SourcePeriodModel.get();
	}

	USE_MESSAGE(Normal);

	//S0 is north west direction, may not used in this program.
	uint16_t S0 (NormalMessage *message)
	{
		uint16_t des1,des2,ran,des;

		dbg("slp-debug", "S0\n");

		//the node is near the left border
		if((message->NodeID-1)%TOPOLOGY_SIZE == 0 && message->NodeID != 1)
		{
			des1 = message->NodeID - TOPOLOGY_SIZE;
			des2 = message->NodeID + 1;

			ran=call Random.rand16()%2;

			if(ran == 0)   des=des1;
			else           des=des2;
		}
		// node is near the bottom
		else if (message->NodeID > 1 && message->NodeID < TOPOLOGY_SIZE)
		{
			des = message->NodeID -1;
		}

		else if (message->NodeID == 1)
		{
			des = message->NodeID + 1;
		}
		//normal nodes
		else
		{
			des1=message->NodeID - 1;
			des2 = message->NodeID - TOPOLOGY_SIZE;

			ran=call Random.rand16()%2;

			if(ran == 0)   des=des1;
			else           des=des2;
		}
		return des;
	}

	//S1 is North East direction
	uint16_t S1 (NormalMessage *message)
	{
	  	uint16_t des1,des2,ran,des;

	  	dbg("slp-debug", "S1\n");

		//the node is near the right border but not the corner node
		if(message->NodeID%TOPOLOGY_SIZE == 0 && message->NodeID != TOPOLOGY_SIZE)
		{
			des1 = message->NodeID - TOPOLOGY_SIZE;
			des2 = message->NodeID - 1;

			ran=call Random.rand16()%2;

			if(ran == 0)   des=des1;
			else           des=des2;
		}
		else if (message->NodeID > 1 && message->NodeID < TOPOLOGY_SIZE)
		{
			des = message->NodeID + 1;
		}

		else if (message->NodeID == TOPOLOGY_SIZE)
		{
			des=TOPOLOGY_SIZE;
		}
		//normal nodes
		else
		{
			des1=message->NodeID + 1;
			des2 = message->NodeID - TOPOLOGY_SIZE;

			ran=call Random.rand16()%2;

			if(ran == 0)   des=des1;
			else           des=des2;
		}
		return des;
	}


	// S2 is South West direction
	uint16_t S2 (NormalMessage *message)
	{
	  	uint16_t des1,des2,ran,des;

	  	dbg("slp-debug", "S2\n");

		//the node is near the left border
		if((message->NodeID-1)%TOPOLOGY_SIZE == 0 && message->NodeID != TOPOLOGY_SIZE * TOPOLOGY_SIZE -TOPOLOGY_SIZE + 1)
		{
			des1 = message->NodeID + TOPOLOGY_SIZE;
			des2 = message->NodeID + 1;

			ran=call Random.rand16()%2;

			if(ran == 0)   des=des1;
			else           des=des2;
		}
		//top
		else if (message->NodeID > TOPOLOGY_SIZE * TOPOLOGY_SIZE -TOPOLOGY_SIZE + 1 && message->NodeID < TOPOLOGY_SIZE * TOPOLOGY_SIZE)
		{
			des = message->NodeID - 1;
		}

		else if (message->NodeID == TOPOLOGY_SIZE * TOPOLOGY_SIZE -TOPOLOGY_SIZE + 1)
		{
			des = TOPOLOGY_SIZE * TOPOLOGY_SIZE -TOPOLOGY_SIZE + 1;
		}
		//normal nodes
		else
		{
			des1=message->NodeID - 1;
			des2 = message->NodeID + TOPOLOGY_SIZE;

			ran=call Random.rand16()%2;

			if(ran == 0)   des=des1;
			else           des=des2;
		}
		return des;
	}

	// S3 is South East direction
	uint16_t S3 (NormalMessage *message)
	{
	  	uint16_t des1,des2,ran,des;

	  	dbg("slp-debug", "S3\n");

		//the node is near the right border
		if(message->NodeID%TOPOLOGY_SIZE == 0 && message->NodeID != TOPOLOGY_SIZE*TOPOLOGY_SIZE)
		{
			des1 = message->NodeID + TOPOLOGY_SIZE;
			des2 = message->NodeID - 1;

			ran=call Random.rand16()%2;

			if(ran == 0)   des=des1;
			else           des=des2;
		}
		//top
		else if (message->NodeID > TOPOLOGY_SIZE * TOPOLOGY_SIZE -TOPOLOGY_SIZE + 1 && message->NodeID < TOPOLOGY_SIZE * TOPOLOGY_SIZE)
		{
			des = message->NodeID +1;
		}
		else if (message->NodeID == TOPOLOGY_SIZE * TOPOLOGY_SIZE)
		{
			des = TOPOLOGY_SIZE * TOPOLOGY_SIZE;   
		}
		//normal nodes
		else
		{
			des1=message->NodeID + 1;
			des2 = message->NodeID + TOPOLOGY_SIZE;

			ran=call Random.rand16()%2;

			if(ran == 0)   des=des1;
			else           des=des2;
		}

		

		return des;
	}

	// x_move is used for SourceCorner or FurtherSinkCorner topology.
	// to make sure the phantom node is away from the sink.
	uint16_t x_move (NormalMessage *message)
	{
	  	uint16_t ran,des;

	  	dbg("slp-debug", "x_move\n");

		//the node has 1-1/5 change to move along the x axis.
		ran=call Random.rand16()%5;

		if (ran == 0)
		{
			if ((message->NodeID+1) >= TOPOLOGY_SIZE*TOPOLOGY_SIZE- TOPOLOGY_SIZE+1)
			{
				des = message->NodeID + 1;
			}
			else
				des = message->NodeID + TOPOLOGY_SIZE;
		}
		else if ((message->NodeID+1)%TOPOLOGY_SIZE == 0)
		{
			des = message->NodeID + TOPOLOGY_SIZE;
		}
		else
			des = message->NodeID + 1;

		return des;
	}

	//y_move is used for SourceCorner or FurtherSinkCorner topology.
	//to make sure the phantom node is away from the sink.
	uint16_t y_move (NormalMessage *message)
	{
	  	uint16_t ran,des;

		dbg("slp-debug", "y_move nid=%u ts=%u\n", message->NodeID, TOPOLOGY_SIZE);

		//the node has 1-1/5 change to move along the y axis.
		ran=call Random.rand16()%5;

		if (ran == 0)
		{
			if ((message->NodeID+1)%TOPOLOGY_SIZE == 0)
			{
				des = message -> NodeID + TOPOLOGY_SIZE;
			}
			else
				des = message->NodeID + 1;
		}
		else if ((message->NodeID+1) >= TOPOLOGY_SIZE*TOPOLOGY_SIZE- TOPOLOGY_SIZE+1)
		{
			des = message->NodeID + 1;
		}
		else
			des = message->NodeID + TOPOLOGY_SIZE;

		return des;
	}

	bool random_walk(NormalMessage* message)
	{
		uint16_t des;
		
		message->NodeID=TOS_NODE_ID;
		
		if (message->flip_coin == 0)
		{
			des = S0(message);
		}
		else if (message->flip_coin == 1)
		{
			des = S1(message);
		}
		else if (message->flip_coin == 2)
		{
			des = S2(message);
		}
		else if (message->flip_coin == 4)
		{
			des = x_move(message);
		}
		else if (message->flip_coin == 5)
		{
			des = y_move(message);
		}
		else
		{     
			des = S3(message);
		}

		message->NodeDes=des;

		/*if (message->NodeDes == TOPOLOGY_SIZE ||
			message->NodeDes == (TOPOLOGY_SIZE * TOPOLOGY_SIZE -TOPOLOGY_SIZE + 1) ||
			message->NodeDes == TOPOLOGY_SIZE * TOPOLOGY_SIZE)
		{
			message->hop = 0;
		}
		else*/
		{
			message->hop -= 1;
		}

		return send_Normal_message(message, message->NodeDes);
	}

	event void Boot.booted()
	{
		dbgverbose("Boot", "%s: Application booted.\n", sim_time_string());

		if (TOS_NODE_ID == SINK_NODE_ID)
		{
			type = SinkNode;
			dbg("Node-Change-Notification", "The node has become a Sink\n");
		}

		call RadioControl.start();
	}

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			dbgverbose("SourceBroadcasterC", "%s: RadioControl started.\n", sim_time_string());

			call ObjectDetector.start();
		}
		else
		{
			dbgerror("SourceBroadcasterC", "%s: RadioControl failed to start, retrying.\n", sim_time_string());

			call RadioControl.start();
		}
	}

	event void RadioControl.stopDone(error_t err)
	{
		dbgverbose("SourceBroadcasterC", "%s: RadioControl stopped.\n", sim_time_string());
	}

	event void ObjectDetector.detect()
	{
		// The sink node cannot become a source node
		if (type != SinkNode)
		{
			dbg_clear("Metric-SOURCE_CHANGE", "set,%u\n", TOS_NODE_ID);
			dbg("Node-Change-Notification", "The node has become a Source\n");

			type = SourceNode;

			call BroadcastNormalTimer.startOneShot(get_source_period());
		}
	}

	event void ObjectDetector.stoppedDetecting()
	{
		if (type == SourceNode)
		{
			call BroadcastNormalTimer.stop();

			type = NormalNode;

			dbg_clear("Metric-SOURCE_CHANGE", "unset,%u\n", TOS_NODE_ID);
			dbg("Node-Change-Notification", "The node has become a Normal\n");
		}
	}

	void generate_message()
	{
		if (!busy)
		{
			NormalMessage message;

			message.NodeID = TOS_NODE_ID;
			message.hop = RANDOM_WALK_HOPS;
			message.hopCounter = 0;

			//add adaptive phantom code here.
			//if (phantom_type == 2)
			{
				if (messageNo % 2 == 0)
					message.hop = RANDOM_WALK_HOPS;
				else
					message.hop = LONG_RANDOM_WALK_HOPS;
			}
			/*else if (phantom_type == 1)
			{
				message->hop = RANDOM_WALK_HOPS;
			}
			else
				printf("wrong phantom type.\n");*/

			//printf("%d ",message.NodeID);

			// the topology are FurtherSinkCorner or SourceCorner, so the random walk is going straight to the sink.
			// it has high change to go through sink neighbor before finishing the random walk phanse.
			/*
			if (SOURCE_NODE_ID_1 < TOPOLOGY_SIZE)
			{
			  flip_coin = 3;
				message->flip_coin = 3;
			}
			*/

			// it makes the phantom node fa away from the sink in the SourceCorner topology.
			// also work for FurtherSinkCorner topology.
			//if (SOURCE_NODE_ID_1 < TOPOLOGY_SIZE)
#ifdef SPACE_BEHIND_SINK
			{
				// random choose the random is whether follow the x axis or y axis.
				uint16_t flip_coin = call Random.rand16()%2;
				if (flip_coin == 0)
				{
					message.flip_coin = 4;
				}
				else
				{
					message.flip_coin = 5;
				}
			}
#else
			//the topology is SinkCorner,so the random walk is far away fro the sink.
			//else
			{
				uint16_t flip_coin=call Random.rand16()%2;	

				if (flip_coin == 0)
					message.flip_coin = 1;
				else
					message.flip_coin = 2;
			}
#endif
			random_walk(&message);
		}

		call BroadcastNormalTimer.startOneShot(get_source_period());
	}


	event void BroadcastNormalTimer.fired()
	{
		messageNo += 1;
		generate_message();  
	}

	bool routing(NormalMessage* message)
	{ 
		error_t status;
		int n_forward,ran;
		int n_horizon;
		int si,sj,ni,nj;

		dbg("slp-debug", "routing\n");

		if (!busy)
		{
			message->NodeID = TOS_NODE_ID;

			// sink position in array,starting with index 0.
			si = SINK_NODE_ID / TOPOLOGY_SIZE;
			if (SINK_NODE_ID % TOPOLOGY_SIZE == 0)
			{
				si-=1;
			}  
			sj = SINK_NODE_ID - si * (TOPOLOGY_SIZE)-1;

			// node position in array,starting with index 0.
			ni = TOS_NODE_ID / TOPOLOGY_SIZE;
			if (TOS_NODE_ID % TOPOLOGY_SIZE == 0)
			{
				ni-=1;
			}
			nj = TOS_NODE_ID - ni * TOPOLOGY_SIZE - 1;

			n_forward = si-ni;
			n_horizon = sj-nj;

			//printf("n_forward=%d,n_horizon%d\n", n_forward,n_horizon);
			
			ran = call Random.rand16()%2;
			
			if(ran == 0)
			{
				if(n_forward > 0)
				{
					message->NodeDes = message->NodeID + TOPOLOGY_SIZE;
				}
				else if(n_forward < 0)
				{
					message->NodeDes = message->NodeID - TOPOLOGY_SIZE;
				}
				else if(n_forward == 0 && n_horizon > 0)
				{
					message->NodeDes = message->NodeID + 1;
				}
				else if (n_forward == 0 && n_horizon < 0)
				{
					message->NodeDes = message->NodeID - 1;
				}
				else 
				{
					dbg("slp-debug","ran=0,n_forward:%d, N_horizon:%d. \n",n_forward,n_horizon);
				}
			}
			else if (ran == 1)
			{
				if(n_horizon > 0)
				{
					message->NodeDes = message->NodeID + 1;
				}
				else if (n_horizon < 0)
				{
					message->NodeDes = message->NodeID - 1;
				}
				else if (n_forward > 0 && n_horizon == 0)
				{
					message->NodeDes = message->NodeID + TOPOLOGY_SIZE;
				}
				else if (n_forward < 0 && n_horizon == 0)
				{
					message->NodeDes = message->NodeID - TOPOLOGY_SIZE;
				}
				else 
				{
					dbg("slp-debug","ran=1,n_forward:%d, N_horizon:%d. \n",n_forward,n_horizon);
				}
			}
			else
			{
				dbg("slp-debug","error in random.\n");
			}   

			//send message phase
			return send_Normal_message(message, message->NodeDes);
		}
		else
		{
			dbg("slp-debug", "%s: BroadcastNormalTimer busy, not sending Normal NormalMessage.\n", sim_time_string());
			return FALSE;
		}
	}  


	void Normal_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		NormalMessage rcm= *(NormalMessage*)rcvd;
		  //int i=0;
		  //int neighbour_nodes[4] ={rcm.NodeDes+TOPOLOGY_SIZE,rcm.NodeDes-TOPOLOGY_SIZE,rcm.NodeDes+1,rcm.NodeDes-1};

		 dbg("slp-debug", "check the received message: NodeID:%d;hop=%d.\n",rcm.NodeID,rcm.hop);

		 if(TOS_NODE_ID != SINK_NODE_ID && rcm.hop <= 0)
		 {

		   dbg("slp-debug",":(flooding_message) message received, from %d to %d.\n",rcm.NodeID,rcm.NodeDes);

		   rcm.hopCounter+=1;

		   //printf("%d ",rcm.NodeDes);

		  /*
			for(i=0; i<4;i++)
				   {
					 if(neighbour_nodes[i]>=1 && neighbour_nodes[i]<TOPOLOGY_SIZE*TOPOLOGY_SIZE)
					 printf("%d ", neighbour_nodes[i]);
				   }
				   */             
			//start routing.
			//printf("%d\n", message);
			routing(&rcm);
		}
		
		else if(rcm.NodeDes == TOS_NODE_ID && TOS_NODE_ID != SINK_NODE_ID && rcm.hop != 0)
		{
			dbg("slp-debug",": (random_walk) message received, from %d, hop=%d.\n",rcm.NodeID,rcm.hop);
			//printf("random walk phase,hop=%d\n",rcm.hop);

			//printf("%d ",rcm.NodeDes);
			rcm.hopCounter+=1;

			dbg("slp-debug", "rcvd rw hopCounter=%d\n",rcm.hopCounter);

			random_walk(&rcm);
		}

		else if (rcm.NodeDes == SINK_NODE_ID)
		{
			//printf("%d ",rcm.NodeDes);
			rcm.hopCounter+=1;            
		}
		else 
		{
			dbg("slp-debug","other: NodeID:%d;NodeDes:%d,hop=%hu.\n",rcm.NodeID,rcm.NodeDes,rcm.hop);
		}
	}

	void Sink_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		// It is helpful to have the sink forward Normal messages onwards
		// Otherwise there is a chance the random walk would terminate at the sink and
		// not flood the network.
		//process_normal(msg, rcvd, source_addr);
	}

	void Source_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
	case SourceNode: Source_receieve_Normal(msg, rcvd, source_addr); break;
	case SinkNode: Sink_receieve_Normal(msg, rcvd, source_addr); break;
	case NormalNode: Normal_receieve_Normal(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)

	// If the sink snoops a normal message, we may as well just deliver it
	void Sink_snoop_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		// TODO: Enable this when the sink can snoop and then correctly
		// respond to a message being received.
		/*if (sequence_number_before(&normal_sequence_counter, rcvd->sequence_number))
		{
			sequence_number_update(&normal_sequence_counter, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			dbgverbose("stdout", "%s: Received unseen Normal by snooping seqno=%u from %u (dsrc=%u).\n",
				sim_time_string(), rcvd->sequence_number, source_addr, rcvd->source_distance + 1);
	}*/
	}

	void x_snoop_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
			//dbgverbose("stdout", "Snooped a normal from %u intended for %u (rcvd-dist=%d, my-dist=%d)\n",
			//  source_addr, call AMPacket.destination(msg), rcvd->landmark_distance_of_sender, landmark_distance);
	}

	// We need to snoop packets that may be unicasted,
	// so the attacker properly responds to them.
	RECEIVE_MESSAGE_BEGIN(Normal, Snoop)
	case SourceNode: x_snoop_Normal(msg, rcvd, source_addr); break;
	case SinkNode: Sink_snoop_Normal(msg, rcvd, source_addr); break;
	case NormalNode: x_snoop_Normal(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)
}
