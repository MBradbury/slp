#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "NormalMessage.h"
#include "DissemMessage.h"

#include "utils.h"

#include <Timer.h>
#include <TinyError.h>

#include <assert.h>
#include <stdlib.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_DISSEM(msg) METRIC_RCV(Dissem, source_addr, msg->source_id, BOTTOM, 1)

#define BOT UINT16_MAX

#define PRINTF(node, ...) if(TOS_NODE_ID==node)simdbg("stdout", __VA_ARGS__);
#define PRINTF0(...) PRINTF(0,__VA_ARGS__)

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;

    uses interface Timer<TMilli> as DissemTimer;
	uses interface Timer<TMilli> as EnqueueNormalTimer;
    uses interface Timer<TMilli> as PreSlotTimer;
    uses interface Timer<TMilli> as SlotTimer;
    uses interface Timer<TMilli> as PostSlotTimer;

	uses interface Pool<NormalMessage> as MessagePool;
	uses interface Queue<NormalMessage*> as MessageQueue;

	uses interface Packet;
	uses interface AMPacket;

	uses interface SplitControl as RadioControl;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;

    uses interface AMSend as DissemSend;
    uses interface Receive as DissemReceive;

	uses interface ObjectDetector;
	uses interface SourcePeriodModel;

	uses interface SequenceNumbers as NormalSeqNos;
}

implementation
{
    //Initialisation variables{{{
    IDList neighbours; // List of one-hop neighbours
    IDList potential_parents;
    OtherList others;
    NeighbourList n_info; // Information about 2-hop neighbours

    uint16_t hop = BOT;
    am_addr_t parent = AM_BROADCAST_ADDR;
    uint16_t slot = BOT;

    bool start = TRUE;
    bool slot_active = FALSE;
    bool normal = TRUE;

    typedef enum
	{
		SourceNode, SinkNode, NormalNode
	} NodeType;

	NodeType type = NormalNode;

	const char* type_to_string()
	{
		switch (type)
		{
		case SourceNode: 			return "SourceNode";
		case SinkNode:				return "SinkNode  ";
		case NormalNode:			return "NormalNode";
		default:					return "<unknown> ";
		}
	}

	uint32_t extra_to_send = 0; //Used in the macros
	bool busy = FALSE; //Used in the macros
	message_t packet; //Used in the macros
    //Initialisation variables}}}

    //Getter Functions{{{
	// This function is to be used by the source node to get the
	// period it should use at the current time.
	// DO NOT use this for nodes other than the source!
	uint32_t get_source_period()
	{
		assert(type == SourceNode);
		return call SourcePeriodModel.get();
	}

    uint32_t get_dissem_period()
    {
        return DISSEM_PERIOD_MS;
    }

    uint32_t get_slot_period()
    {
        return SLOT_PERIOD_MS;
    }

    uint32_t get_tdma_num_slots()
    {
        return TDMA_NUM_SLOTS;
    }

    uint32_t get_assignment_interval()
    {
        return SLOT_ASSIGNMENT_INTERVAL;
    }
    //###################}}}

    //Startup Events{{{
	event void Boot.booted()
	{
        neighbours = IDList_new();
        potential_parents = IDList_new();
        others = OtherList_new();
        n_info = NeighbourList_new();

		simdbgverbose("Boot", "%s: Application booted.\n", sim_time_string());

		if (TOS_NODE_ID == SINK_NODE_ID)
		{
			type = SinkNode;
			simdbg("Node-Change-Notification", "The node has become a Sink\n");
		}

		call RadioControl.start();
	}

    void init();
	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			simdbgverbose("SourceBroadcasterC", "%s: RadioControl started.\n", sim_time_string());

            init();
            call ObjectDetector.start();
            call DissemTimer.startOneShot(get_dissem_period());
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

            call EnqueueNormalTimer.startOneShot(get_source_period());
		}
	}

	event void ObjectDetector.stoppedDetecting()
	{
		if (type == SourceNode)
		{
            call EnqueueNormalTimer.stop();

			type = NormalNode;

			simdbg_clear("Metric-SOURCE_CHANGE", "unset,%u\n", TOS_NODE_ID);
			simdbg("Node-Change-Notification", "The node has become a Normal\n");
		}
	}

    //Startup Events}}}

    //Main Logic{{{

	USE_MESSAGE(Normal);
    USE_MESSAGE(Dissem);

    void init()
    {
        if (type == SinkNode)
        {
            int i;
            for(i=0; i<neighbours.count; i++)
            {
                simdbg("stdout", "NEVER CALLED\n"); //Because no neighbours discovered initially
                NeighbourList_add(&n_info, neighbours.ids[i], BOT, BOT);
            }
            
            hop = 0;
            parent = AM_BROADCAST_ADDR;
            slot = get_tdma_num_slots(); //Delta

            start = FALSE;

            NeighbourList_add(&n_info, TOS_NODE_ID, 0, slot);
        }
        else
        {
            NeighbourList_add(&n_info, TOS_NODE_ID, BOT, BOT); // TODO: Should this be added to the algorithm
        }

        IDList_add(&neighbours, TOS_NODE_ID); // TODO: Should this be added to the algorithm
    }


    void process_dissem()
    {
        int i;
        simdbg("stdout", "Processing DISSEM...\n");
        if(slot == BOT && type != SinkNode)
        {
            NeighbourInfo* info = NeighbourList_info_for_min_hop(&n_info, &potential_parents);
            OtherInfo* other_info;

            if (info == NULL) {
                /*simdbg("stdout", "Info was NULL.\n");*/
                return;
            }
            simdbg("stdout", "Info was: ID=%u, hop=%u, slot=%u.\n", info->id, info->hop, info->slot);

            other_info = OtherList_get(&others, info->id);
            if(other_info == NULL) {
                simdbg("stdout", "Other info was NULL.\n");
                return;
            }

            hop = info->hop + 1;
            parent = info->id; //info->slot is equivalent to parent slot
            slot = info->slot - rank(&(other_info->N), TOS_NODE_ID) - get_assignment_interval() - 1;

            simdbg("stdout", "Chosen parent %u.\n", parent);
            simdbg("stdout", "Chosen slot %u.\n", slot);

            NeighbourList_add(&n_info, TOS_NODE_ID, hop, slot);
        }

        for(i=0; i<n_info.count; i++)
        {
            const NeighbourInfo* n_info_i = &n_info.info[i];
            // Check if there is a slot collision with a neighbour
            // Do not check for slot collisions with ourself
            if(n_info_i->slot == slot && n_info_i->id != TOS_NODE_ID)
            {
                // To make sure only one node resolves the slot (rather than both)
                // Have the node further from the sink resolve.
                // If nodes have the same distance use the node id as a tie breaker.
                if((hop > n_info_i->hop) || (hop == n_info_i->hop && TOS_NODE_ID > n_info_i->id))
                {
                    slot = slot - 1;
                    NeighbourList_add(&n_info, TOS_NODE_ID, hop, slot);

                    simdbg("stdout", "Adjusted slot of current node to %u because node %u has slot %u.\n",
                        slot, n_info_i->id, n_info_i->slot);
                }
            }
        }
    }

    void send_dissem()
    {
        DissemMessage msg;
        msg.source_id = TOS_NODE_ID;
        msg.normal = normal;
        NeighbourList_select(&n_info, &neighbours, &(msg.N)); //TODO Explain this to Arshad

        send_Dissem_message(&msg, AM_BROADCAST_ADDR);
    }

	task void send_normal()
	{
		NormalMessage* message;

        // This task may be delayed, such that it is scheduled when the slot is active,
        // but called after the slot is no longer active.
        // So it is important to check here if the slot is still active before sending.
        if (!slot_active)
        {
            return;
        }

		simdbgverbose("SourceBroadcasterC", "%s: BroadcastTimer fired.\n", sim_time_string());

		message = call MessageQueue.dequeue();

		if (message != NULL)
		{
            error_t send_result = send_Normal_message_ex(message, AM_BROADCAST_ADDR);
			if (send_result == SUCCESS)
			{
				call MessagePool.put(message);
			}
			else
			{
				simdbgerror("stdout", "send failed with code %u, not returning memory to pool so it will be tried again\n", send_result);
			}

            if (slot_active && !(call MessageQueue.empty()))
            {
                post send_normal();
            }
		}
	}

    //Main Logic}}}

    //Timers.fired(){{{
    event void DissemTimer.fired()
    {
        /*PRINTF0("%s: BeaconTimer fired.\n", sim_time_string());*/
        if(slot != BOT) send_dissem();
        process_dissem();
        call PreSlotTimer.startOneShot(get_dissem_period());
    }

    event void PreSlotTimer.fired()
    {
        uint16_t s = (slot == BOT) ? get_tdma_num_slots() : slot;
        /*PRINTF0("%s: PreSlotTimer fired.\n", sim_time_string());*/
        call SlotTimer.startOneShot(s*get_slot_period());
    }


    event void SlotTimer.fired()
    {
        /*PRINTF0("%s: SlotTimer fired.\n", sim_time_string());*/
        slot_active = TRUE;
        if(slot != BOT)
        {
            post send_normal();
        }
        call PostSlotTimer.startOneShot(get_slot_period());
    }

    event void PostSlotTimer.fired()
    {
        uint16_t s = (slot == BOT) ? get_tdma_num_slots() : slot;
        /*PRINTF0("%s: PostSlotTimer fired.\n", sim_time_string());*/
        slot_active = FALSE;
        call DissemTimer.startOneShot((get_tdma_num_slots()-(s-1))*get_slot_period());
    }

    event void EnqueueNormalTimer.fired()
    {
        /*simdbg("stdout", "%s: EnqueueNormalTimer fired.\n", sim_time_string());*/
        if(slot != BOT)
        {
            NormalMessage* message;

            message = call MessagePool.get();
            if (message != NULL)
            {
                message->sequence_number = call NormalSeqNos.next(TOS_NODE_ID);
                message->source_distance = 0;
                message->source_id = TOS_NODE_ID;

                if (call MessageQueue.enqueue(message) != SUCCESS)
                {
                    simdbgerror("stdout", "Failed to enqueue, should not happen!\n");
                }
                else
                {
                    call NormalSeqNos.increment(TOS_NODE_ID);
                }
            }
            else
            {
                simdbgerror("stdout", "No pool space available for another Normal message.\n");
                simdbg_clear("Metric-Pool-Full", "%u\n", TOS_NODE_ID);
            }
        }

        call EnqueueNormalTimer.startOneShot(get_source_period());
    }
    //}}} Timers.fired()

    //Receivers{{{
	void Normal_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
        /*simdbg("stdout", "Received normal.\n");*/
		if (call NormalSeqNos.before(TOS_NODE_ID, rcvd->sequence_number))
		{
			NormalMessage* forwarding_message;

			call NormalSeqNos.update(TOS_NODE_ID, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);

			forwarding_message = call MessagePool.get();
			if (forwarding_message != NULL)
			{
				*forwarding_message = *rcvd;
				forwarding_message->source_distance += 1;

				if (call MessageQueue.enqueue(forwarding_message) != SUCCESS)
				{
					simdbgerror("stdout", "Failed to enqueue, should not happen!\n");
				}
			}
			else
			{
				simdbgerror("stdout", "No pool space available for another Normal message.\n");
			}
		}
	}

	void Sink_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
        simdbg("stdout", "SINK RECEIVED NORMAL.\n");
		if (call NormalSeqNos.before(TOS_NODE_ID, rcvd->sequence_number))
		{
			call NormalSeqNos.update(TOS_NODE_ID, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
        case SourceNode: break;
		case SinkNode: Sink_receive_Normal(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Normal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)

    void x_receive_Dissem(const DissemMessage* const rcvd, am_addr_t source_addr)
    {
        int i;
        NeighbourInfo* source;
        NeighbourList rcvdList;

        METRIC_RCV_DISSEM(rcvd);

        OnehopList_to_NeighbourList(&(rcvd->N), &rcvdList);
        source = NeighbourList_get(&rcvdList, source_addr);

        IDList_add(&neighbours, source_addr);

        if(rcvd->normal)
        {
            if(slot == BOT && source->slot != BOT)
            {
                OtherInfo* info;

                IDList_add(&potential_parents, source_addr);

                info = OtherList_get(&others, source_addr);
                if(info == NULL)
                {
                    OtherList_add(&others, OtherInfo_new(source_addr));
                    info = OtherList_get(&others, source_addr);
                }

                for(i=0; i<rcvd->N.count; i++)
                {
                    if(rcvd->N.info[i].slot == BOT)
                    {
                        IDList_add(&(info->N), rcvdList.info[i].id);
                    }
                }
            }

            for(i = 0; i<rcvd->N.count; i++)
            {
                if(rcvd->N.info[i].slot != BOT)
                {
                    NeighbourList_add_info(&n_info, rcvdList.info[i]);
                }
            }
        }
        else
        {
            if(parent == source_addr)
            {
                /*if(slot >= NeighbourList_get(&(rcvd->N), source_addr)->slot)*/
                if(slot >= source->slot)
                {
                    /*slot = NeighbourList_get(&(rcvd->N), source_addr)->slot - (NeighbourList_get(&n_info, parent)->slot - NeighbourList_get(&(rcvd->N), parent)->slot);*/
                    slot = source->slot - (NeighbourList_get(&n_info, parent)->slot - source->slot);
                    normal = FALSE;
                }
                /*NeighbourList_add_info(&n_info, *NeighbourList_get(&(rcvd->N), source_addr));*/
                NeighbourList_add_info(&n_info, *source);
            }
        }
    }

    void Sink_receive_Dissem(const DissemMessage* const rcvd, am_addr_t source_addr)
    {
        int i;

        METRIC_RCV_DISSEM(rcvd);

        IDList_add(&neighbours, source_addr);

        for(i = 0; i<rcvd->N.count; i++)
        {
            NeighbourList_add_info(&n_info, rcvd->N.info[i]);
        }
    }


    RECEIVE_MESSAGE_BEGIN(Dissem, Receive)
        case SourceNode:
        case NormalNode: x_receive_Dissem(rcvd, source_addr); break;
        case SinkNode  : Sink_receive_Dissem(rcvd, source_addr); break;
    RECEIVE_MESSAGE_END(Dissem)
    //}}}Receivers
}
