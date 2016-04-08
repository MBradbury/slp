#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "NormalMessage.h"
#include "Parameters.h"

#include <Timer.h>
#include <TinyError.h>
#include <assert.h>
#include <stdlib.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)

//#define NORTH_WEST_DIRECTION 0
//#define NORTH_EAST_DIRECTION 1
//#define SOUTH_WEST_DIRECTION 2
//#define SOUTH_EAST_DIRECTION 3
//#define BIASED_X_AXIS        4
//#define BIASED_Y_AXIS        5

//#define SHORT_RANDOM_MESSAGE 0
//#define LONG_RANDOM_MESSAGE  1
//#define TRUE 1
//#define FALSE 0

//define the global vaiable.
//make it work for multiple sources.
uint16_t random_walk_message_no = 1;
uint16_t message_current_type = LONG_RANDOM_MESSAGE;
uint16_t message_previous_type = LONG_RANDOM_MESSAGE;

/////////////////////////////
//#define WAIT_BEFORE_SHORT TRUE
//uint16_t short_long[] = {1,1};
/////////////////////////////

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


	uint16_t random_neighbour_node_chosen_seclect (NormalMessage *message, uint16_t choose)
	{
		uint16_t neighbour_west_node, neighbour_east_node, neighbour_north_node, neighbour_south_node; 
		uint16_t neighbour_node_chosen = 0;
		uint16_t random_number,biased_random_number;


		neighbour_west_node = TOS_NODE_ID -1;
		neighbour_east_node = TOS_NODE_ID + 1;
		neighbour_north_node = TOS_NODE_ID - TOPOLOGY_SIZE;
		neighbour_south_node = TOS_NODE_ID + TOPOLOGY_SIZE;

		random_number=call Random.rand16()%2;

		biased_random_number=call Random.rand16()%BIASED_RANDOM_WALK_FACTOR;

		switch(choose)
		{
			case(NORTH_WEST_DIRECTION):
    			if (left_border(TOS_NODE_ID)) 					neighbour_node_chosen = neighbour_north_node;
    			else if (bottom(TOS_NODE_ID)) 					neighbour_node_chosen = neighbour_west_node;
    			else if (left_bottom_corner(TOS_NODE_ID)) 		neighbour_node_chosen = TOS_NODE_ID; //stop here.
    			else 											neighbour_node_chosen=(random_number==0)?neighbour_west_node:neighbour_north_node;
      			break;

    		case(NORTH_EAST_DIRECTION):
    			if (bottom(TOS_NODE_ID)) 												neighbour_node_chosen = neighbour_east_node;
    			else if (right_bottom_corner(TOS_NODE_ID))								neighbour_node_chosen = neighbour_south_node;
    			// for SinkCorner
    			else if (right_border(TOS_NODE_ID))              									neighbour_node_chosen = neighbour_south_node;
    			else      																neighbour_node_chosen=(random_number==0)?neighbour_east_node:neighbour_north_node;
  				break;

  			case(SOUTH_WEST_DIRECTION):
    			if (left_border(TOS_NODE_ID))  					neighbour_node_chosen = neighbour_south_node;
    			// for SinkCorner
    			else if(top(TOS_NODE_ID))						neighbour_node_chosen = neighbour_east_node;				
    			else if(left_top_corner(TOS_NODE_ID))			neighbour_node_chosen = neighbour_east_node;
    			else 											neighbour_node_chosen=(random_number==0)?neighbour_west_node:neighbour_south_node;
    			break;

    		case(SOUTH_EAST_DIRECTION):
    			if (right_bottom_corner(TOS_NODE_ID)||right_border(TOS_NODE_ID))  	neighbour_node_chosen = neighbour_south_node;
    			else if (left_top_corner(TOS_NODE_ID) || top(TOS_NODE_ID)) 			neighbour_node_chosen = neighbour_east_node;
    			else if (right_top_corner(TOS_NODE_ID))								neighbour_node_chosen = TOS_NODE_ID; //add stop code here.
    			else																neighbour_node_chosen=(random_number==0)?neighbour_east_node:neighbour_south_node;
      			break;

      		case(BIASED_X_AXIS):
      			
    			if(biased_random_number == 0)
    			//small possibility follow the y axis.
    			{
    				//simdbg("slp-debug",": (x)y move.\n");
      				neighbour_node_chosen = (top(TOS_NODE_ID) || left_top_corner(TOS_NODE_ID)) ? neighbour_east_node:neighbour_south_node;
    			}
    			else
    			//high possibility follow the x axis.
    			{
    				//simdbg("slp-debug",": (x)x move.\n");
      				neighbour_node_chosen = (right_border(TOS_NODE_ID) || right_bottom_corner(TOS_NODE_ID)) ? neighbour_south_node:neighbour_east_node;
    			}
    			break;

    		case(BIASED_Y_AXIS):
    			if (biased_random_number == 0)
    			//small possibility follow the x axis.
    			{
    				//simdbg("slp-debug",": (y)x move.\n");
    				neighbour_node_chosen = (right_border(TOS_NODE_ID)||right_bottom_corner(TOS_NODE_ID)) ? neighbour_south_node:neighbour_east_node;
    			}
    			else
    			//high possibility follow the y axis.
    			{
    				//simdbg("slp-debug",": (y)y move.\n");
      				neighbour_node_chosen = (top(TOS_NODE_ID) || left_top_corner(TOS_NODE_ID)) ? neighbour_east_node:neighbour_south_node;    
				}
    			break;
		}

		return neighbour_node_chosen;
	}

	bool random_walk(NormalMessage* message)
	{
		message->target = random_neighbour_node_chosen_seclect (message, message->random_walk_direction);

		//message->target = neighbour_node_chosen;

		if (message_reach_corner(message->target))
		{
			message->random_walk_hop_remaining = 0;
		}
		else
		{
			message->random_walk_hop_remaining -= 1;
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
	uint16_t short_long_sequence_random_walk(uint16_t m, uint16_t n)
	{
		uint16_t random_walk_remaining;
		uint16_t seq_reminder = random_walk_message_no % (m+n);

		if( seq_reminder% (m+n) <= m && seq_reminder % (m+n) != 0)
		{
			random_walk_remaining = RANDOM_WALK_HOPS;
			message_current_type = SHORT_RANDOM_MESSAGE;
		}
		else
		{
			random_walk_remaining = LONG_RANDOM_WALK_HOPS;
			message_current_type = LONG_RANDOM_MESSAGE;
		}

		if((seq_reminder-1)% (m+n) <= m && (seq_reminder-1) % (m+n) != 0)
		{
			message_previous_type = SHORT_RANDOM_MESSAGE;
		}
		else
		{
			message_previous_type = LONG_RANDOM_MESSAGE;
		}
			
		random_walk_message_no += 1;

		return random_walk_remaining;		
	}

	uint16_t long_short_sequence_random_walk(uint16_t m, uint16_t n)
	{
		uint16_t random_walk_remaining;
		uint16_t seq_reminder = random_walk_message_no % (m+n);

		if( seq_reminder% (m+n) <= m && seq_reminder % (m+n) != 0)
		{
			random_walk_remaining = LONG_RANDOM_WALK_HOPS;
			message_current_type = LONG_RANDOM_MESSAGE;
		}
		else
		{
			random_walk_remaining = RANDOM_WALK_HOPS;
			message_current_type = SHORT_RANDOM_MESSAGE;
		}

		if((seq_reminder-1)% (m+n) <= m && (seq_reminder-1) % (m+n) != 0)
		{
			message_previous_type = LONG_RANDOM_MESSAGE;
		}
		else
		{
			message_previous_type = SHORT_RANDOM_MESSAGE;
		}
			
		random_walk_message_no += 1;

		return random_walk_remaining;
	}

	void generate_message()
	{
		typedef enum random_walk_possible_directions
		{

			S_nw, S_ne, S_ws, S_se,Biased_x_axis, Biased_y_axis

		} random_walk_direction;

		random_walk_direction random_walk_direction_chosen;

		uint16_t flip_coin = call Random.rand16()%2;

		if (!busy)
		{
			
			NormalMessage message;
			message.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);			
			message.source_id = TOS_NODE_ID;
			message.source_distance = 0;

			//add adaptive phantom code here.
			#if SHORT_LONG_SEQUENCE && LONG_SHORT_SEQUENCE
			{
				simdbgerror("only need one sequence!");
				exit(-1);
			}
			#if SHORT_LONG_SEQUENCE
				message.random_walk_hop_remaining = short_long_sequence_random_walk(short_long[0],short_long[1]);
			#elif LONG_SHORT_SEQUENCE
				message.random_walk_hop_remaining = long_short_sequence_random_walk(short_long[0],short_long[1]);
			#else
				{
				simdbgerror("need one sequence!");
				exit(-1);
				}
			#endif

		//SPACE_BEHIND_SINK means more space behind the sink.
		//fit for Source Corner.  
		#ifdef SPACE_BEHIND_SINK
			{
				//if random walk length is shorter than the source sink distance, biased random walk is no need to implement.
				//normally the short random walk is set to less than half of source sink distance.
				if (message.random_walk_hop_remaining < TOPOLOGY_SIZE)
				{
					simdbg("slp-debug","short random walk, message number:%d, last random walk flag:%d, sim time:%s\n",message.sequence_number, random_walk_message_no,sim_time_string());
					//random_walk_direction_chosen = S_se;
					message.random_walk_direction = random_walk_direction_chosen = S_se;
				}
				else
				{
					//randomly choose the random is whether follow the x axis or y axis.
					random_walk_direction_chosen = (flip_coin == 0)? Biased_x_axis : Biased_y_axis;
					message.random_walk_direction = random_walk_direction_chosen;
					simdbg("slp-debug","long random walk, message number:%d, last random walk flag:%d, sim time:%s\n",message.sequence_number,random_walk_message_no,sim_time_string());
				}
			}
		//fit for the situation that the sink is located in the corner or in the border, NO_SPACE_BEHIND_SINK.
		//fit for SinkCorner or FurtherSinkCorner
		#else
			{
				// fit for FurtherSinkCorner.
				//ensure all source ID is les than TOPOLOGY_SIZE*3, even with 3 sources.
				if (message.source_id < TOPOLOGY_SIZE*3)
				{					
					if (message.random_walk_hop_remaining < TOPOLOGY_SIZE)
					{
						simdbg("slp-debug","short random walk, message number:%d, last random walk flag:%d, sim time:%s\n",message.sequence_number, random_walk_message_no,sim_time_string());	
						message.random_walk_direction = random_walk_direction_chosen = S_se;
					}
					else
					{
						message.random_walk_direction = random_walk_direction_chosen = S_se;
						//message.random_walk_direction = (flip_coin == 0)?4:5;
						simdbg("slp-debug","long random walk, message number:%d, last random walk flag:%d, sim time:%s\n",message.sequence_number,random_walk_message_no,sim_time_string());
					}
				}

				//fit for SinkCorner.
				//biased random walk is not applied here.
				else
				{
					if(message.random_walk_hop_remaining < TOPOLOGY_SIZE)
						simdbg("slp-debug","short random walk, message number:%d, last random walk flag:%d, sim time:%s\n",message.sequence_number, random_walk_message_no,sim_time_string());
					else
						simdbg("slp-debug","long random walk, message number:%d, last random walk flag:%d, sim time:%s\n",message.sequence_number,random_walk_message_no,sim_time_string());	
					//message.random_walk_direction = call Random.rand16()%4;
					random_walk_direction_chosen = (flip_coin == 0)? S_ne: S_ws;
					message.random_walk_direction = random_walk_direction_chosen;
				}
				
			}
#endif
			if (random_walk(&message))
			{
				
				call NormalSeqNos.increment(TOS_NODE_ID);
			}
		}

		// if next message is short random walk, wait for the WAIT_BEFORE_SHORT_MS time.
		if(WAIT_BEFORE_SHORT == TRUE && RANDOM_WALK_HOPS < LONG_RANDOM_WALK_HOPS && \
			message_previous_type ==LONG_RANDOM_MESSAGE && message_current_type == SHORT_RANDOM_MESSAGE)
			call BroadcastNormalTimer.startOneShot(WAIT_BEFORE_SHORT_MS + get_source_period());
		else
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

			//simdbg("slp-debug", "check the received message: NodeID:%d;random_walk_hop_remaining=%d.\n",source_addr,rcm.random_walk_hop_remaining);

			if(rcm.random_walk_hop_remaining == 0 && rcm.target != SINK_NODE_ID)
			{

				//simdbg("slp-debug",":rcm.target:%d, rcm.random_walk_hop_remaining:%d,SINK_NODE_ID:%d.\n",rcm.target,rcm.random_walk_hop_remaining,SINK_NODE_ID);

				rcm.source_distance+=1;
	         
				flooding(&rcm);
			}
			else if(rcm.target == TOS_NODE_ID && TOS_NODE_ID != SINK_NODE_ID && rcm.random_walk_hop_remaining != 0)
			{
				//simdbg("slp-debug",": (random_walk) message received, from %d, random_walk_hop_remaining=%d.\n",source_addr,rcm.random_walk_hop_remaining);

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
				//simdbg("slp-debug","other: NodeID:%d;target:%d,random_walk_hop_remaining=%hu.\n",source_addr,rcm.target,rcm.random_walk_hop_remaining);
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
			//  source_addr, call AMPacket.neighbour_node_chosentination(msg), rcvd->landmark_distance_of_sender, landmark_distance);
	}

	// We need to snoop packets that may be unicasted,
	// so the attacker properly responds to them.
	RECEIVE_MESSAGE_BEGIN(Normal, Snoop)
	case SourceNode: x_snoop_Normal(msg, rcvd, source_addr); break;
	case SinkNode: Sink_snoop_Normal(msg, rcvd, source_addr); break;
	case NormalNode: x_snoop_Normal(msg, rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)
}
