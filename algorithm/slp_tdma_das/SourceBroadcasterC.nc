#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "NormalMessage.h"
#include "DissemMessage.h"
#include "SearchMessage.h"
#include "ChangeMessage.h"
#include "EmptyNormalMessage.h"

#include "utils.h"

#include <Timer.h>
#include <TinyError.h>

#include <stdlib.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_DISSEM(msg) METRIC_RCV(Dissem, source_addr, source_addr, BOTTOM, 1)
#define METRIC_RCV_SEARCH(msg) METRIC_RCV(Search, source_addr, source_addr, BOTTOM, 1)
#define METRIC_RCV_CHANGE(msg) METRIC_RCV(Change, source_addr, source_addr, BOTTOM, 1)
#define METRIC_RCV_EMPTYNORMAL(msg) METRIC_RCV(EmptyNormal, source_addr, msg->source_id, msg->sequence_number, 1)

#define BOT UINT16_MAX

#define PRINTF(node, ...) if(TOS_NODE_ID==node)simdbg("stdout", __VA_ARGS__);
#define PRINTF0(...) PRINTF(0,__VA_ARGS__)

//Distance search messages travel from sink
#define PR_DIST 8

//Length of phantom route
#define PR_LENGTH 10 //Half sink-source distance/safety period (which is 5 for 11x11)
#define SEARCH_PERIOD_COUNT 24

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;
    uses interface Random;
    uses interface LocalTime<TMilli>;

    uses interface Timer<TMilli> as DissemTimer;
    uses interface Timer<TMilli> as DissemTimerSender;
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

    uses interface AMSend as SearchSend;
    uses interface Receive as SearchReceive;

    uses interface AMSend as ChangeSend;
    uses interface Receive as ChangeReceive;

    uses interface AMSend as EmptyNormalSend;
    uses interface Receive as EmptyNormalReceive;

    uses interface MetricLogging;

    uses interface NodeType;
	uses interface MessageType;
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
    IDList children;
    uint16_t slot = BOT;

    bool start = TRUE;
    bool slot_active = FALSE;
    bool normal = TRUE;

    uint32_t period_counter = 0;
    int dissem_sending;
    bool start_node = FALSE;
    uint32_t redir_length = 0;

    enum
	{
		SourceNode, SinkNode, NormalNode, SearchNode, ChangeNode
	};

    // Produces a random float between 0 and 1
    float random_float(void)
    {
        // There appears to be problem with the 32 bit random number generator
        // in TinyOS that means it will not generate numbers in the full range
        // that a 32 bit integer can hold. So use the 16 bit value instead.
        // With the 16 bit integer we get better float values to compared to the
        // fake source probability.
        // Ref: https://github.com/tinyos/tinyos-main/issues/248
        const uint16_t rnd = call Random.rand16();

        return ((float)rnd) / UINT16_MAX;
    }

    uint16_t choose(const IDList* list)
    {
        if (list->count == 0) return UINT16_MAX;
        else return list->ids[(call Random.rand16()) % list->count];
    }

	uint32_t extra_to_send = 0; //Used in the macros
	bool busy = FALSE; //Used in the macros
	message_t packet; //Used in the macros
    //Initialisation variables}}}

    //Getter Functions{{{
    uint32_t get_dissem_period(void)
    {
        return DISSEM_PERIOD_MS;
    }

    uint32_t get_slot_period(void)
    {
        return SLOT_PERIOD_MS;
    }

    uint32_t get_tdma_num_slots(void)
    {
        return TDMA_NUM_SLOTS;
    }

    uint32_t get_assignment_interval(void)
    {
        return SLOT_ASSIGNMENT_INTERVAL;
    }

    uint32_t get_minimum_setup_periods(void)
    {
        return TDMA_SETUP_PERIODS;
    }

    uint32_t get_pre_beacon_periods(void)
    {
        return TDMA_PRE_BEACON_PERIODS;
    }

    uint32_t get_dissem_timeout(void)
    {
        return TDMA_DISSEM_TIMEOUT;
    }

    uint32_t get_pr_dist()
    {
        return PR_DIST;
    }

    uint32_t get_pr_length()
    {
        return PR_LENGTH;
    }
    //###################}}}

    //Startup Events{{{
	event void Boot.booted()
	{
        neighbours = IDList_new();
        potential_parents = IDList_new();
        others = OtherList_new();
        n_info = NeighbourList_new();
        children = IDList_new();

		simdbgverbose("Boot", "Application booted.\n");

        call MessageType.register_pair(NORMAL_CHANNEL, "Normal");
        call MessageType.register_pair(DISSEM_CHANNEL, "Dissem");
        call MessageType.register_pair(SEARCH_CHANNEL, "Search");
        call MessageType.register_pair(CHANGE_CHANNEL, "Change");
        call MessageType.register_pair(EMPTYNORMAL_CHANNEL, "EmptyNormal");

        call NodeType.register_pair(SourceNode, "SourceNode");
        call NodeType.register_pair(SinkNode, "SinkNode");
        call NodeType.register_pair(NormalNode, "NormalNode");
        call NodeType.register_pair(SearchNode, "SearchNode");
        call NodeType.register_pair(ChangeNode, "ChangeNode");

        if (call NodeType.is_node_sink())
        {
            call NodeType.init(SinkNode);
        }
        else
        {
            call NodeType.init(NormalNode);
        }

		call RadioControl.start();
	}

    void init();
	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			simdbgverbose("SourceBroadcasterC", "RadioControl started.\n");

            init();
            call ObjectDetector.start();
            call DissemTimer.startOneShot(get_dissem_period());
		}
		else
		{
			ERROR_OCCURRED(ERROR_RADIO_CONTROL_START_FAIL, "RadioControl failed to start, retrying.\n");

			call RadioControl.start();
		}
	}

	event void RadioControl.stopDone(error_t err)
	{
		simdbgverbose("SourceBroadcasterC", "RadioControl stopped.\n");
	}

    event void ObjectDetector.detect()
    {
        // A sink node cannot become a source node
        if (call NodeType.get() != SinkNode)
        {
            call NodeType.set(SourceNode);

            call SourcePeriodModel.startPeriodic();
        }
    }

    event void ObjectDetector.stoppedDetecting()
    {
        if (call NodeType.get() == SourceNode)
        {
            call SourcePeriodModel.stop();

            call NodeType.set(NormalNode);
        }
    }

    //Startup Events}}}

    //Main Logic{{{

	USE_MESSAGE(Normal);
    USE_MESSAGE(Dissem);
    USE_MESSAGE(Search);
    USE_MESSAGE(Change);
    USE_MESSAGE(EmptyNormal);

    void init(void)
    {
        if (call NodeType.get() == SinkNode)
        {
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
        dissem_sending = get_dissem_timeout();
    }

    void process_dissem(void)
    {
        int i;
        //simdbg("stdout", "Processing DISSEM...\n");
        if(slot == BOT)
        {
            const NeighbourInfo* parent_info = NeighbourList_info_for_min_hop(&n_info, &potential_parents);
            OtherInfo* other_info;

            if (parent_info == NULL) {
                /*simdbg("stdout", "Info was NULL.\n");*/
                return;
            }
            simdbg("stdout", "Info for n-info with min hop was: ID=%u, hop=%u, slot=%u.\n",
                parent_info->id, parent_info->hop, parent_info->slot);

            other_info = OtherList_get(&others, parent_info->id);
            if(other_info == NULL) {
                simdbgerror("stdout", "Other info was NULL.\n");
                return;
            }

            hop = parent_info->hop + 1;
            parent = parent_info->id;
            slot = parent_info->slot - rank(&(other_info->N), TOS_NODE_ID) - get_assignment_interval() - 1;

            simdbg("stdout", "OtherList: "); IDList_print(&(other_info->N)); simdbg_clear("stdout", "\n");

            simdbg("stdout", "Updating parent to %u, slot to %u and hop to %u.\n", parent, slot, hop);

            NeighbourList_add(&n_info, TOS_NODE_ID, hop, slot);
        }

    }

    void process_collision(void)
    {
        if (slot != BOT)
        {
            OnehopList neighbour_info;
            int i,j;
            NeighbourList_select(&n_info, &neighbours, &neighbour_info);
            simdbg("stdout", "Checking Neighbours for slot collisions (our slot %u / hop %u): ", slot, hop); NeighbourList_print(&n_info); simdbg_clear("stdout", "\n");

            for(i=0; i<n_info.count; i++)
            {
                const NeighbourInfo* n_info_i = &n_info.info[i];
                // Check if there is a slot collision with a neighbour
                // Do not check for slot collisions with ourself
                if(n_info_i->slot == slot && n_info_i->id != TOS_NODE_ID)
                {

                    simdbg("stdout", "Found colliding slot from node %u, will evaluate if (%u || (%u && %u))\n",
                        n_info_i->id, (hop > n_info_i->hop), (hop == n_info_i->hop), (TOS_NODE_ID > n_info_i->id));

                    // To make sure only one node resolves the slot (rather than both)
                    // Have the node further from the sink resolve.
                    // If nodes have the same distance use the node id as a tie breaker.
                    if((hop > n_info_i->hop) || (hop == n_info_i->hop && TOS_NODE_ID > n_info_i->id))
                    {
                        slot = slot - 1;
                        NeighbourList_add(&n_info, TOS_NODE_ID, hop, slot);

                        simdbg("stdout", "Adjusted slot of current node to %u because node %u has slot %u.\n",
                            slot, n_info_i->id, n_info_i->slot);
                        dissem_sending = get_dissem_timeout();
                    }
                }
            }

            simdbg("stdout", "Checking for collisions between neighbours.\n");
            for(i=0; i < n_info.count; i++)
            {
                if(n_info.info[i].slot == BOT)
                {
                    dissem_sending = get_dissem_timeout();
                    break;
                }

                for(j=i+1; j < n_info.count; j++)
                {
                    if(n_info.info[i].slot == n_info.info[j].slot)
                    {
                        simdbg("stdout", "Detected collision between %u and %u\n", n_info.info[i].id, n_info.info[j].id);
                        break;
                    }
                }
            }

            //Check to see if DAS has been broken
            for(i=0; i < neighbour_info.count; i++)
            {
                if(neighbour_info.info[i].id == parent) {
                    if(neighbour_info.info[i].slot < slot) {
                        simdbg("DAS-State", "DAS is 0\n");
                        break;
                    }
                }
            }
            /*
             *simdbg("stdout", "Checking for collisions between neighbours.\n");
             *for(i=0; i < neighbour_info.count; i++)
             *{
             *    for(j=i+1; j < neighbour_info.count; j++)
             *    {
             *        if(neighbour_info.info[i].slot == neighbour_info.info[j].slot)
             *        {
             *        }
             *    }
             *}
             */
        }
    }

    event void DissemTimerSender.fired()
    {
        if(dissem_sending>0)
        {
            DissemMessage msg;
            msg.normal = normal;
            msg.parent = parent;
            NeighbourList_select(&n_info, &neighbours, &(msg.N));

            simdbg("stdout", "Sending dissem with: "); OnehopList_print(&(msg.N)); simdbg_clear("stdout", "\n");

            send_Dissem_message(&msg, AM_BROADCAST_ADDR);
            dissem_sending--;
        }
        if(period_counter < get_pre_beacon_periods()) dissem_sending = get_dissem_timeout();
    }

    void send_search_init()
    {
        if(call NodeType.get() == SinkNode)
        {
            int i;
            SearchMessage msg;
            msg.pr = get_pr_length();
            msg.dist = get_pr_dist() - 1;
            msg.a_node = BOT;
            assert(children.count != 0);
            for(i=0; i<children.count; i++) {
                if(rank(&children, children.ids[i]) == children.count)
                {
                    msg.a_node = children.ids[i];
                    break;
                }
            }
            send_Search_message(&msg, AM_BROADCAST_ADDR);
            simdbg("stdout", "Sent search message to %u\n", msg.a_node);
        }
    }
    /*void send_search_init()*/
    /*{*/
        /*if(call NodeType.get() == SinkNode)*/
        /*{*/
            /*int i;*/
            /*SearchMessage msg;*/
            /*msg.pr = get_pr_length();*/
            /*msg.dist = get_pr_dist() - 1;*/
            /*send_Search_message(&msg, AM_BROADCAST_ADDR);*/
            /*simdbg("stdout", "Sent search message\n");*/
        /*}*/
    /*}*/

    void send_change_init()
    {
        if(start_node && redir_length > 0)
        {
            ChangeMessage msg;
            IDList npar = IDList_minus_parent(&potential_parents, parent);
            OnehopList onehop;
            simdbg("stdout", "CHANGE HAS BEGUN\n");
            start_node = FALSE;
            NeighbourList_select(&n_info, &neighbours, &onehop);
            msg.a_node = choose(&npar); //choose(&potential_parents); //choose(&npar);
            msg.n_slot = OnehopList_min_slot(&onehop);
            msg.len_d = redir_length - 1;
            send_Change_message(&msg, AM_BROADCAST_ADDR);
            /*simdbg("Node-Change-Notification", "The node has become a TFS\n");*/
            call NodeType.set(ChangeNode);
        }
    }

	task void send_normal(void)
	{
		NormalMessage* message;

        // This task may be delayed, such that it is scheduled when the slot is active,
        // but called after the slot is no longer active.
        // So it is important to check here if the slot is still active before sending.
        if (!slot_active)
        {
            return;
        }

		simdbgverbose("SourceBroadcasterC", "BroadcastTimer fired.\n");

		message = call MessageQueue.dequeue();

		if (message != NULL)
		{
            error_t send_result;
            /*message->sequence_number = call NormalSeqNos.next(TOS_NODE_ID);*/
            message->sequence_number = period_counter;
            send_result = send_Normal_message_ex(message, AM_BROADCAST_ADDR);
			if (send_result == SUCCESS)
			{
				call MessagePool.put(message);
			}
			else
			{
				simdbgerror("stdout", "send failed with code %u, not returning memory to pool so it will be tried again\n", send_result);
			}

            /*if (slot_active && !(call MessageQueue.empty()))*/
            /*{*/
                /*post send_normal();*/
            /*}*/
		}
        else
        {
            EmptyNormalMessage msg;
            /*msg.sequence_number = call NormalSeqNos.next(TOS_NODE_ID);*/
            msg.sequence_number = period_counter;
            msg.source_id = TOS_NODE_ID;
            send_EmptyNormal_message(&msg, AM_BROADCAST_ADDR);
            /*call NormalSeqNos.increment(TOS_NODE_ID);*/
        }
	}

    void MessageQueue_clear()
    {
        NormalMessage* message;
        while(!(call MessageQueue.empty()))
        {
            message = call MessageQueue.dequeue();
            if(message)
            {
                call MessagePool.put(message);
            }
        }
    }
    //Main Logic}}}

    //Timers.fired(){{{
    event void DissemTimer.fired()
    {
        /*PRINTF0("%s: BeaconTimer fired.\n", sim_time_string());*/
        uint32_t now = call LocalTime.get();
        period_counter++;
        call NormalSeqNos.increment(TOS_NODE_ID);
        if(call NodeType.get() != SourceNode) MessageQueue_clear(); //XXX Dirty hack to stop other nodes sending stale messages
        if(period_counter == SEARCH_PERIOD_COUNT)
        {
            send_search_init();
            call DissemTimer.startOneShotAt(now, get_dissem_period());
            return;
        }
        else if(period_counter == SEARCH_PERIOD_COUNT+1)
        {
            send_change_init();
            call DissemTimer.startOneShotAt(now, 2*get_dissem_period());
            return;
        }
        if(slot != BOT || period_counter < get_pre_beacon_periods())
        {
            call DissemTimerSender.startOneShotAt(now, (uint32_t)(get_slot_period() * random_float()));
        }

        if(period_counter > get_pre_beacon_periods())
        {
            process_dissem();
            process_collision();
        }
        call PreSlotTimer.startOneShotAt(now, get_dissem_period());
    }

    event void PreSlotTimer.fired()
    {
        uint32_t now = call LocalTime.get();
        const uint16_t s = (slot == BOT) ? get_tdma_num_slots() : slot;
        /*PRINTF0("%s: PreSlotTimer fired.\n", sim_time_string());*/
        call SlotTimer.startOneShotAt(now, s*get_slot_period());
    }


    event void SlotTimer.fired()
    {
        /*PRINTF0("%s: SlotTimer fired.\n", sim_time_string());*/
        uint32_t now = call LocalTime.get();
        slot_active = TRUE;
        if(slot != BOT && call NodeType.get() != SinkNode && period_counter > get_minimum_setup_periods())
        {
            post send_normal();
        }
        call PostSlotTimer.startOneShotAt(now, get_slot_period());
    }

    event void PostSlotTimer.fired()
    {
        uint32_t now = call LocalTime.get();
        const uint16_t s = (slot == BOT) ? get_tdma_num_slots() : slot;
        /*PRINTF0("%s: PostSlotTimer fired.\n", sim_time_string());*/
        slot_active = FALSE;
        call DissemTimer.startOneShotAt(now, (get_tdma_num_slots() - (s-1)) * get_slot_period());
    }

    event void SourcePeriodModel.fired()
    {
        /*simdbg("stdout", "SourcePeriodModel fired.\n");*/
        if(slot != BOT && period_counter > get_minimum_setup_periods())
        {
            NormalMessage* message;

            message = call MessagePool.get();
            if (message != NULL)
            {
                /*message->sequence_number = call NormalSeqNos.next(TOS_NODE_ID);*/
                message->source_distance = 0;
                message->source_id = TOS_NODE_ID;

                if (call MessageQueue.enqueue(message) != SUCCESS)
                {
                    simdbgerror("stdout", "Failed to enqueue, should not happen!\n");
                }
                else
                {
                    /*call NormalSeqNos.increment(TOS_NODE_ID);*/
                }
            }
            else
            {
                ERROR_OCCURRED(ERROR_POOL_FULL, "No pool space available for another Normal message.\n");
            }
        }
    }
    //}}} Timers.fired()

    //Receivers{{{
	void Normal_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
        /*simdbg("stdout", "Received normal.\n");*/
		if (call NormalSeqNos.before(TOS_NODE_ID, rcvd->sequence_number))
		{
			NormalMessage* forwarding_message;

			/*call NormalSeqNos.update(TOS_NODE_ID, rcvd->sequence_number);*/

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
				ERROR_OCCURRED(ERROR_POOL_FULL, "No pool space available for another Normal message.\n");
			}
		}
	}

	void Sink_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
        simdbg("stdout", "SINK RECEIVED NORMAL.\n");
		if (call NormalSeqNos.before(TOS_NODE_ID, rcvd->sequence_number))
		{
			/*call NormalSeqNos.update(TOS_NODE_ID, rcvd->sequence_number);*/

			METRIC_RCV_NORMAL(rcvd);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
        case SourceNode: break;
		case SinkNode: Sink_receive_Normal(rcvd, source_addr); break;
        case SearchNode:
        case ChangeNode:
		case NormalNode: Normal_receive_Normal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)

    void x_receive_Dissem(const DissemMessage* const rcvd, am_addr_t source_addr)
    {
        int i;
        const NeighbourInfo* source;
        NeighbourList rcvdList;

        METRIC_RCV_DISSEM(rcvd);

        OnehopList_to_NeighbourList(&(rcvd->N), &rcvdList);
        source = NeighbourList_get(&rcvdList, source_addr);

        if(rcvd->parent == TOS_NODE_ID)
        {
            IDList_add(&children, source_addr);
            simdbg("stdout", "Added child to list: "); IDList_print(&children); simdbg_clear("stdout", "\n");
        }

        // Record that the sender is in our 1-hop neighbourhood
        IDList_add(&neighbours, source_addr);
        if(NeighbourList_get(&n_info, source_addr) == NULL)
        {
            NeighbourList_add(&n_info, source_addr, BOT, BOT);
        }

        if(rcvd->normal)
        {
            if(slot == BOT && source->slot != BOT)
            {
                OtherInfo* others_source_addr;

                IDList_add(&potential_parents, source_addr);

                others_source_addr = OtherList_get(&others, source_addr);
                if(others_source_addr == NULL)
                {
                    OtherList_add(&others, OtherInfo_new(source_addr));
                    others_source_addr = OtherList_get(&others, source_addr);
                }

                for(i=0; i<rcvd->N.count; i++)
                {
                    if(rcvd->N.info[i].slot == BOT)
                    {
                        IDList_add(&(others_source_addr->N), rcvdList.info[i].id);
                    }
                }
            }

            for(i = 0; i<rcvd->N.count; i++)
            {
                if(rcvd->N.info[i].slot != BOT && rcvd->N.info[i].id != TOS_NODE_ID) //XXX Collision fix is here
                {
                    NeighbourInfo* oldinfo = NeighbourList_get(&n_info, rcvd->N.info[i].id);
                    if(oldinfo == NULL || (rcvd->N.info[i].slot != oldinfo->slot && rcvd->N.info[i].slot < oldinfo->slot)) //XXX Stops stale data?
                    {
                        dissem_sending = get_dissem_timeout();
                        NeighbourList_add_info(&n_info, &rcvd->N.info[i]);
                    }
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
                NeighbourList_add_info(&n_info, source);
            }
        }
    }

    void Sink_receive_Dissem(const DissemMessage* const rcvd, am_addr_t source_addr)
    {
        int i;

        METRIC_RCV_DISSEM(rcvd);

        IDList_add(&neighbours, source_addr);

        if(rcvd->parent == TOS_NODE_ID)
        {
            IDList_add(&children, source_addr);
            simdbg("stdout", "Added child to list: "); IDList_print(&children); simdbg_clear("stdout", "\n");
        }

        for(i = 0; i<rcvd->N.count; i++)
        {
            NeighbourList_add_info(&n_info, &rcvd->N.info[i]);
        }

    }


    RECEIVE_MESSAGE_BEGIN(Dissem, Receive)
        case SourceNode:
        case SearchNode:
        case ChangeNode:
        case NormalNode: x_receive_Dissem(rcvd, source_addr); break;
        case SinkNode  : Sink_receive_Dissem(rcvd, source_addr); break;
    RECEIVE_MESSAGE_END(Dissem)

    void Normal_receive_Search(const SearchMessage* const rcvd, am_addr_t source_addr)
    {
        IDList npar = IDList_minus_parent(&potential_parents, parent);
        METRIC_RCV_SEARCH(rcvd);
        if(rcvd->a_node != TOS_NODE_ID) return;
        simdbg("stdout", "Received search\n");

        if((rcvd->dist == 0 && npar.count != 0) || children.count == 0)
        {
            start_node = TRUE;
            redir_length = rcvd->pr;
            simdbg("stdout", "Search messages ended\n");
            /*simdbg("Node-Change-Notification", "The node has become a PFS\n");*/
        }
        else if(rcvd->dist > 0 || npar.count == 0)
        {
            int i;
            SearchMessage msg;
            msg.pr = rcvd->pr;
            msg.dist = (rcvd->dist-1<0) ? 0 : rcvd->dist - 1;
            msg.a_node = BOT;
            for(i=0; i<children.count; i++) {
                if(rank(&children, children.ids[i]) == children.count)
                {
                    msg.a_node = children.ids[i];
                    break;
                }
            }
            send_Search_message(&msg, AM_BROADCAST_ADDR);
            simdbg("stdout", "Sent search message again to %u\n", msg.a_node);
            /*simdbg("Node-Change-Notification", "The node has become a PFS\n");*/
            call NodeType.set(SearchNode);
        }
    }
    /*void Normal_receive_Search(const SearchMessage* const rcvd, am_addr_t source_addr)*/
    /*{*/
        /*METRIC_RCV_SEARCH(rcvd);*/
        /*if(parent == source_addr)*/
        /*{*/
            /*OtherInfo* other_info = OtherList_get(&others, parent);*/
            /*if(rank(&(other_info->N), TOS_NODE_ID) == other_info->N.count)*/
            /*{*/
                /*IDList npar = IDList_minus_parent(&potential_parents, parent);*/
                /*simdbg("stdout", "Received search\n");*/
                /*if((rcvd->dist == 0) && (npar.count != 0))*/
                /*{*/
                    /*start_node = TRUE;*/
                    /*redir_length = rcvd->pr;*/
                /*}*/
                /*else if ((rcvd->dist > 0) || (npar.count == 0))*/
                /*{*/
                    /*SearchMessage msg;*/
                    /*msg.dist = ((rcvd->dist-1) < 0) ? 0 : rcvd->dist-1;*/
                    /*msg.pr = rcvd->pr;*/
                    /*send_Search_message(&msg, AM_BROADCAST_ADDR);*/
                    /*call NodeType.set(SearchNode);*/
                /*}*/
            /*}*/
        /*}*/
    /*}*/

    RECEIVE_MESSAGE_BEGIN(Search, Receive)
        case SourceNode: break;
        case SearchNode:
        case ChangeNode:
        case NormalNode: Normal_receive_Search(rcvd, source_addr); break;
        case SinkNode:   break;
    RECEIVE_MESSAGE_END(Search)

    void Normal_receive_Change(const ChangeMessage* const rcvd, am_addr_t source_addr)
    {
        IDList npar;
        METRIC_RCV_CHANGE(rcvd);
        if(rcvd->a_node != TOS_NODE_ID) return;
        npar = IDList_minus_parent(&potential_parents, parent);
        npar = IDList_minus_parent(&npar, source_addr);
        if(rcvd->len_d > 0 && rcvd->a_node == TOS_NODE_ID && npar.count != 0)
        {
            ChangeMessage msg;
            OnehopList onehop;
            simdbg("stdout", "Received change\n");
            slot = rcvd->n_slot - 1;
            NeighbourList_add(&n_info, TOS_NODE_ID, hop, slot); //Update own information before processing
            NeighbourList_get(&n_info, source_addr)->slot = rcvd->n_slot; //Update source_addr node with new slot information
            NeighbourList_select(&n_info, &neighbours, &onehop);
            dissem_sending = get_dissem_timeout(); //Restart sending dissem messages
            msg.n_slot = OnehopList_min_slot(&onehop);
            msg.a_node = choose(&npar);
            /*if(npar.count != 0)*/
            /*{*/
                /*msg.a_node = choose(&npar);*/
            /*}*/
            /*else*/
            /*{*/
                /*IDList potential_receivers = IDList_minus_parent(&neighbours, source_addr);*/
                /*msg.a_node = choose(&potential_receivers);*/
            /*}*/
            msg.len_d = rcvd->len_d - 1;
            send_Change_message(&msg, AM_BROADCAST_ADDR);
            /*simdbg("Node-Change-Notification", "The node has become a TFS\n");*/
            call NodeType.set(ChangeNode);
            simdbg("stdout", "Next a_node is %u\n", msg.a_node);
        }
        else if(rcvd->len_d == 0 && rcvd->a_node == TOS_NODE_ID)
        {
            normal = FALSE;
            slot = rcvd->n_slot - 1; //get_assignment_interval(); //rcvd->n_slot - 1;
            NeighbourList_add(&n_info, TOS_NODE_ID, hop, slot);
            dissem_sending = get_dissem_timeout(); //Restart sending dissem messages
            simdbg("stdout", "Change messages ended\n");
            /*simdbg("Node-Change-Notification", "The node has become a TFS\n");*/
            call NodeType.set(ChangeNode);
        }
        simdbg("stdout", "a_node=%u, len_d=%u, n_slot=%u\n", rcvd->a_node, rcvd->len_d, rcvd->n_slot);

    }

    RECEIVE_MESSAGE_BEGIN(Change, Receive)
        case SourceNode: break;
        case SearchNode:
        case ChangeNode:
        case NormalNode: Normal_receive_Change(rcvd, source_addr); break;
        case SinkNode:   break;
    RECEIVE_MESSAGE_END(Change)

    void x_receive_EmptyNormal(const EmptyNormalMessage* const rcvd, am_addr_t source_addr)
    {
        METRIC_RCV_EMPTYNORMAL(rcvd);
    }

    RECEIVE_MESSAGE_BEGIN(EmptyNormal, Receive)
        case SourceNode:
        case SearchNode:
        case ChangeNode:
        case NormalNode:
        case SinkNode:   x_receive_EmptyNormal(rcvd, source_addr); break;
    RECEIVE_MESSAGE_END(EmptyNormal)
}
