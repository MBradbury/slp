#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "NormalMessage.h"

#include <Timer.h>
#include <TinyError.h>

#include <assert.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)

//define the global vaiable.
//make it work for multiple sources.
uint16_t last_random_walk = 1;
uint16_t short_long[] = {1,2};

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

  	bool left_bottom_corner(uint16_t messageID)		{return (messageID==0)?TRUE:FALSE;}

  	bool right_bottom_corner(uint16_t messageID)	{return (messageID==TOPOLOGY_SIZE-1)?TRUE:FALSE;}

  	bool left_top_corner(uint16_t messageID)		{return (messageID==TOPOLOGY_SIZE*(TOPOLOGY_SIZE-1))?TRUE:FALSE;}

  	bool right_top_corner(uint16_t messageID)		{return (messageID==TOPOLOGY_SIZE*TOPOLOGY_SIZE-1)?TRUE:FALSE;}



 	bool left_border(uint16_t messageID)			{return (messageID%TOPOLOGY_SIZE==0 && messageID!=0 && messageID!=TOPOLOGY_SIZE*(TOPOLOGY_SIZE-1))?TRUE:FALSE;}

  	bool right_border(uint16_t messageID)			{return ((messageID+1)%TOPOLOGY_SIZE == 0 && messageID!=TOPOLOGY_SIZE-1 && messageID!=TOPOLOGY_SIZE*TOPOLOGY_SIZE-1)?TRUE:FALSE;}

  	bool bottom(uint16_t messageID)					{return (messageID>0 && messageID<TOPOLOGY_SIZE-1)?TRUE:FALSE;}

  	bool top(uint16_t messageID)					{return (messageID>TOPOLOGY_SIZE*(TOPOLOGY_SIZE-1) && messageID<TOPOLOGY_SIZE*TOPOLOGY_SIZE-1)?TRUE:FALSE;}

  	bool message_reach_corner(uint16_t messageID)	{return (messageID==0||messageID==TOPOLOGY_SIZE-1||messageID==TOPOLOGY_SIZE*(TOPOLOGY_SIZE-1)||messageID==TOPOLOGY_SIZE*TOPOLOGY_SIZE-1)?TRUE:FALSE;}


	uint16_t random_des_seclect (NormalMessage *message, uint16_t choose)
	{
		uint16_t des1,des2,des3,des4;
		uint16_t des = 0;
		uint16_t ran,biased_ran;

		des1 = TOS_NODE_ID -1;
		des2 = TOS_NODE_ID + 1;
		des3 = TOS_NODE_ID - TOPOLOGY_SIZE;
		des4 = TOS_NODE_ID + TOPOLOGY_SIZE;

		ran=call Random.rand16()%2;

		biased_ran=call Random.rand16()%10;

		switch(choose)
		{
			case(0):
    			if (left_border(TOS_NODE_ID)) 					des = des3;
    			else if (bottom(TOS_NODE_ID)) 					des = des1;
    			else if (left_bottom_corner(TOS_NODE_ID)) 		des = TOS_NODE_ID; //stop here.
    			else 											des=(ran==0)?des1:des3;
      			break;

    		case(1):
    			if (bottom(TOS_NODE_ID)) 												des = des2;
    			else if (right_bottom_corner(TOS_NODE_ID))								des = des4;
    			// for SinkCorner
    			else if (right_border(TOS_NODE_ID)) 									des = des4;
    			else      																des=(ran==0)?des2:des3;
  				break;

  			case(2):
    			if (left_border(TOS_NODE_ID))  					des = des4;
    			// for SinkCorner
    			else if(top(TOS_NODE_ID))						des = des2;				
    			else if(left_top_corner(TOS_NODE_ID))			des = des2;
    			else 											des=(ran==0)?des1:des4;
    			break;

    		case(3):
    			if (right_bottom_corner(TOS_NODE_ID)||right_border(TOS_NODE_ID))  	des = des4;
    			else if (left_top_corner(TOS_NODE_ID) || top(TOS_NODE_ID)) 			des = des2;
    			else if (right_top_corner(TOS_NODE_ID))								des = TOS_NODE_ID; //add stop code here.
    			else																des=(ran==0)?des2:des4;
      			break;

      		case(4):
      			
    			if(biased_ran == 0)
    			//small possibility follow the y axis.
    			{
    				//simdbg("slp-debug",": (x)y move.\n");
      				des = (top(TOS_NODE_ID) || left_top_corner(TOS_NODE_ID)) ? des2:des4;
    			}
    			else
    			//high possibility follow the x axis.
    			{
    				//simdbg("slp-debug",": (x)x move.\n");
      				des = (right_border(TOS_NODE_ID) || right_bottom_corner(TOS_NODE_ID)) ? des4:des2;
    			}
    			break;

    		case(5):
    			if (biased_ran == 0)
    			//small possibility follow the x axis.
    			{
    				//simdbg("slp-debug",": (y)x move.\n");
    				des = (right_border(TOS_NODE_ID)||right_bottom_corner(TOS_NODE_ID)) ? des4:des2;
    			}
    			else
    			//high possibility follow the y axis.
    			{
    				//simdbg("slp-debug",": (y)y move.\n");
      				des = (top(TOS_NODE_ID) || left_top_corner(TOS_NODE_ID)) ? des2:des4;    
				}
    			break;
		}

		return des;
	}

	bool random_walk(NormalMessage* message)
	{
		message->target = random_des_seclect (message, message->flip_coin);

		//message->target = des;

		if (message_reach_corner(message->target))
		{
			message->walk_distance_remaining = 0;
		}
		else
		{
			message->walk_distance_remaining -= 1;
		}

		return send_Normal_message(message, message->target);
	}

	event void Boot.booted()
	{
		simdbgverbose("Boot", "%s: Application booted.\n", sim_time_string());

		if (TOS_NODE_ID == SINK_NODE_ID)
		{
			type = SinkNode;
			simdbg("Node-Change-Notification", "The node has become a Sink\n");
		}

		call RadioControl.start();
	}

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			simdbgverbose("SourceBroadcasterC", "%s: RadioControl started.\n", sim_time_string());

			call ObjectDetector.start();
		}
		else
		{
			simdbgerror("SourceBroadcasterC", "%s: RadioControl failed to start, retrying.\n", sim_time_string());

			call RadioControl.start();
		}
	}

	event void RadioControl.stopDone(error_t err)
	{
		simdbgverbose("SourceBroadcasterC", "%s: RadioControl stopped.\n", sim_time_string());
	}

	event void ObjectDetector.detect()
	{
		// The sink node cannot become a source node
		if (type != SinkNode)
		{
			simdbg_clear("Metric-SOURCE_CHANGE", "set,%u\n", TOS_NODE_ID);
			simdbg("Node-Change-Notification", "The node has become a Source\n");

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

			simdbg_clear("Metric-SOURCE_CHANGE", "unset,%u\n", TOS_NODE_ID);
			simdbg("Node-Change-Notification", "The node has become a Normal\n");
		}
	}

	//m short random walk and n long random walk messages combination.
	uint16_t message_mshort_nlong(uint16_t m, uint16_t n)
	{
		uint16_t random_walk_remaining;

		random_walk_remaining = (last_random_walk % (m+n) <= m && last_random_walk % (m+n) != 0)? RANDOM_WALK_HOPS : LONG_RANDOM_WALK_HOPS;
		last_random_walk += 1;

		return random_walk_remaining;
	}

	void generate_message()
	{
		uint16_t flip_coin = call Random.rand16()%2;
		if (!busy)
		{
			
			NormalMessage message;
			message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);			
			message.source_id = TOS_NODE_ID;
			message.source_distance = 0;

			//add adaptive phantom code here.
			message.walk_distance_remaining = message_mshort_nlong(short_long[0],short_long[1]);

		//SPACE_BEHIND_SINK means more space behind the sink.
		//fit for Source Corner.  
		#ifdef SPACE_BEHIND_SINK
			{
				//if random walk length is shorter than the source sink distance, biased random walk is no need to implement.
				//normally the short random walk is set to less than half of source sink distance.
				if (message.walk_distance_remaining < TOPOLOGY_SIZE)
				{
					simdbg("slp-debug","short random walk, message number:%d, last random walk flag:%d, sim time:%s\n",message.sequence_number, last_random_walk,sim_time_string());
					message.flip_coin = 3;
				}
				else
				{
					//randomly choose the random is whether follow the x axis or y axis.
					message.flip_coin = (flip_coin == 0)?4:5;
					simdbg("slp-debug","long random walk, message number:%d, last random walk flag:%d, sim time:%s\n",message.sequence_number,last_random_walk,sim_time_string());
				}
			}
		//fit for the situation that the sink is located in the corner or in the border.
		//fit for SinkCorner or FurtherSinkCorner
		#else
			{
				// FurtherSinkCorner codes here.
				//ensure all source ID is les than TOPOLOGY_SIZE*2, even with 3 sources.
				if (message.source_id < TOPOLOGY_SIZE*2)
				{					
					if (message.walk_distance_remaining < TOPOLOGY_SIZE)
					{
						simdbg("slp-debug","short random walk, message number:%d, last random walk flag:%d, sim time:%s\n",message.sequence_number, last_random_walk,sim_time_string());	
						message.flip_coin = 3;
					}
					else
					{
						message.flip_coin = 3;
						//message.flip_coin = (flip_coin == 0)?4:5;
						simdbg("slp-debug","long random walk, message number:%d, last random walk flag:%d, sim time:%s\n",message.sequence_number,last_random_walk,sim_time_string());
					}
				}

				//SinkCorner codes here.
				//biased random walk is not applied here.
				else
				{
					if(message.walk_distance_remaining < TOPOLOGY_SIZE)
						simdbg("slp-debug","short random walk, message number:%d, last random walk flag:%d, sim time:%s\n",message.sequence_number, last_random_walk,sim_time_string());
					else
						simdbg("slp-debug","long random walk, message number:%d, last random walk flag:%d, sim time:%s\n",message.sequence_number,last_random_walk,sim_time_string());	
					//message.flip_coin = call Random.rand16()%4;
					message.flip_coin = (flip_coin == 0)?1:2;
				}
				
			}
#endif
			if (random_walk(&message))
			{
				
				call NormalSeqNos.increment(TOS_NODE_ID);
			}
		}

		call BroadcastNormalTimer.startOneShot(get_source_period());
	}


	event void BroadcastNormalTimer.fired()
	{
		
		generate_message();  
	}



	bool flooding(NormalMessage* message)
	{
		return send_Normal_message(message, AM_BROADCAST_ADDR);
	}


	void Normal_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		NormalMessage rcm= *(NormalMessage*)rcvd;

		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);
			
			METRIC_RCV_NORMAL(rcvd);

			//simdbg("slp-debug", "check the received message: NodeID:%d;walk_distance_remaining=%d.\n",source_addr,rcm.walk_distance_remaining);

			if(rcm.walk_distance_remaining == 0 && rcm.target != SINK_NODE_ID)
			{

				//simdbg("slp-debug",":rcm.target:%d, rcm.walk_distance_remaining:%d,SINK_NODE_ID:%d.\n",rcm.target,rcm.walk_distance_remaining,SINK_NODE_ID);

				rcm.source_distance+=1;
	         
				flooding(&rcm);
			}
			else if(rcm.target == TOS_NODE_ID && TOS_NODE_ID != SINK_NODE_ID && rcm.walk_distance_remaining != 0)
			{
				//simdbg("slp-debug",": (random_walk) message received, from %d, walk_distance_remaining=%d.\n",source_addr,rcm.walk_distance_remaining);

				rcm.source_distance+=1;

				//simdbg("slp-debug", "rcvd rw source_distance=%d\n",rcm.source_distance);

				random_walk(&rcm);
			}
			else if (rcm.target == SINK_NODE_ID)
			{
				rcm.source_distance+=1;            
			}
			else 
			{
				//simdbg("slp-debug","other: NodeID:%d;target:%d,walk_distance_remaining=%hu.\n",source_addr,rcm.target,rcm.walk_distance_remaining);
			}
		}
	}

	void Sink_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);
		}
	}

	void Source_receieve_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
		if (call NormalSeqNos.before(rcvd->source_id, rcvd->sequence_number))
		{
			call NormalSeqNos.update(rcvd->source_id, rcvd->sequence_number);
			
			METRIC_RCV_NORMAL(rcvd);
		}
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
		/*
			METRIC_RCV_NORMAL(rcvd);
		*/
	}

	void x_snoop_Normal(message_t* msg, const NormalMessage* const rcvd, am_addr_t source_addr)
	{
			//simdbgverbose("stdout", "Snooped a normal from %u intended for %u (rcvd-dist=%d, my-dist=%d)\n",
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
