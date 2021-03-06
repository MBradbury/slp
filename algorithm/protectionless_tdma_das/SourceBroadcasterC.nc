#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"
#include "HopDistance.h"

#include "NormalMessage.h"
#include "DissemMessage.h"
#include "EmptyNormalMessage.h"

#include "utils.h"

#include <Timer.h>
#include <TinyError.h>

#include <stdlib.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, hop_distance_increment(msg->source_distance))
#define METRIC_RCV_DISSEM(msg) METRIC_RCV(Dissem, source_addr, source_addr, UNKNOWN_SEQNO, 1)
#define METRIC_RCV_EMPTYNORMAL(msg) METRIC_RCV(EmptyNormal, source_addr, source_addr, msg->sequence_number, 1)

#define BOT UINT16_MAX

#define PRINTF(node, ...) if(TOS_NODE_ID==node)simdbgverbose("stdout", __VA_ARGS__);
#define PRINTF0(...) PRINTF(0,__VA_ARGS__)

#define LOG_FUNC(label) simdbg("stdout", "%s: %s\n", label, __FUNCTION__)
#define S() LOG_FUNC("START")
#define E() LOG_FUNC("END")

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;
    uses interface Crc;
    uses interface Random;
    uses interface LocalTime<TMilli>;

    uses interface Timer<TMilli> as DissemTimerSender;

	uses interface Pool<NormalMessage> as MessagePool;
	uses interface Queue<NormalMessage*> as MessageQueue;

	uses interface Packet;
	uses interface AMPacket;

	uses interface SplitControl as RadioControl;

	uses interface AMSend as NormalSend;
	uses interface Receive as NormalReceive;

    uses interface AMSend as DissemSend;
    uses interface Receive as DissemReceive;

    uses interface AMSend as EmptyNormalSend;
    uses interface Receive as EmptyNormalReceive;

    uses interface MetricLogging;
	uses interface MetricHelpers;

    uses interface TDMA;

    uses interface NodeType;
	uses interface MessageType;
	uses interface ObjectDetector;
	uses interface SourcePeriodModel;

	uses interface SequenceNumbers as NormalSeqNos;
	uses interface SequenceNumbers as EmptyNormalSeqNos;
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

    bool start = TRUE;
    bool normal = TRUE;

    uint32_t period_counter = 0;
    /*int dissem_sending;*/

    // Produces a random float between 0 and 1
    /*float random_float(void)*/
    /*{*/
        /*// There appears to be problem with the 32 bit random number generator*/
        /*// in TinyOS that means it will not generate numbers in the full range*/
        /*// that a 32 bit integer can hold. So use the 16 bit value instead.*/
        /*// With the 16 bit integer we get better float values to compared to the*/
        /*// fake source probability.*/
        /*// Ref: https://github.com/tinyos/tinyos-main/issues/248*/
        /*const uint16_t rnd = call Random.rand16();*/

        /*return ((float)rnd) / UINT16_MAX;*/
    /*}*/

    uint16_t random_interval(uint16_t min, uint16_t max)
    {
        return min + call Random.rand16() / (UINT16_MAX / (max - min + 1) + 1);
    }

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

    /*uint32_t get_dissem_timeout(void)*/
    /*{*/
        /*return TDMA_DISSEM_TIMEOUT;*/
    /*}*/
    //###################}}}

    //Setter Functions{{{
    event void TDMA.slot_changed(uint16_t old_slot, uint16_t new_slot)
    {
        NeighbourList_add(&n_info, TOS_NODE_ID, hop, call TDMA.get_slot());
    }

    void set_hop(uint16_t new_hop)
    {
        hop = new_hop;
        NeighbourList_add(&n_info, TOS_NODE_ID, hop, call TDMA.get_slot());
    }

    /*void set_dissem_timer(void)*/
    /*{*/
        /*dissem_sending = get_dissem_timeout();*/
    /*}*/
    //###################}}}

    //Startup Events{{{
	event void Boot.booted()
	{
        neighbours = IDList_new();
        potential_parents = IDList_new();
        others = OtherList_new();
        n_info = NeighbourList_new();

        call MessageType.register_pair(NORMAL_CHANNEL, "Normal");
        call MessageType.register_pair(DISSEM_CHANNEL, "Dissem");
        call MessageType.register_pair(EMPTYNORMAL_CHANNEL, "EmptyNormal");

        call NodeType.register_pair(SourceNode, "SourceNode");
        call NodeType.register_pair(SinkNode, "SinkNode");
        call NodeType.register_pair(NormalNode, "NormalNode");

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

    void init(void);

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			LOG_STDOUT_VERBOSE(EVENT_RADIO_ON, "radio on\n");

            init();
            call ObjectDetector.start();
            call TDMA.start();
		}
		else
		{
			ERROR_OCCURRED(ERROR_RADIO_CONTROL_START_FAIL, "RadioControl failed to start, retrying.\n");

			call RadioControl.start();
		}
	}

	event void RadioControl.stopDone(error_t err)
	{
		LOG_STDOUT_VERBOSE(EVENT_RADIO_OFF, "radio off\n");
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

	USE_MESSAGE_WITH_CALLBACK_NO_EXTRA_TO_SEND(Normal);
    USE_MESSAGE_NO_EXTRA_TO_SEND(Dissem);
    USE_MESSAGE_NO_EXTRA_TO_SEND(EmptyNormal);

    void init(void)
    {
        if (call NodeType.get() == SinkNode)
        {
            parent = AM_BROADCAST_ADDR;
            set_hop(0);
            call TDMA.set_slot(get_tdma_num_slots());

            start = FALSE;
        }
        else
        {
            set_hop(BOT);
            call TDMA.set_slot(BOT);
        }

        IDList_add(&neighbours, TOS_NODE_ID); // TODO: Should this be added to the algorithm
        /*set_dissem_timer();*/
    }


    void process_dissem(void)
    {
        int i;
        //simdbgverbose("stdout", "Processing DISSEM...\n");
        if(call TDMA.get_slot() == BOT)
        {
            const NeighbourInfo* parent_info = NeighbourList_info_for_min_hop(&n_info, &potential_parents);
            OtherInfo* other_info;

            if (parent_info == NULL) {
                /*simdbgverbose("stdout", "Info was NULL.\n");*/
                return;
            }
            simdbgverbose("stdout", "Info for n-info with min hop was: ID=%u, hop=%u, slot=%u.\n",
                parent_info->id, parent_info->hop, parent_info->slot);

            other_info = OtherList_get(&others, parent_info->id);
            if(other_info == NULL) {
                simdbgerrorverbose("stdout", "Other info was NULL.\n");
                return;
            }

            parent = parent_info->id;
            set_hop(parent_info->hop + 1);
            call TDMA.set_slot(parent_info->slot - rank(&(other_info->N), TOS_NODE_ID) - get_assignment_interval() - 1);

            simdbgverbose("stdout", "OtherList: "); IDList_print(&(other_info->N)); simdbgverbose_clear("stdout", "\n");

            simdbgverbose("stdout", "Updating parent to %u, slot to %u and hop to %u.\n", parent, call TDMA.get_slot(), hop);
        }
    }

    void process_collision(void)
    {
        if (call TDMA.get_slot() != BOT)
        {
            OnehopList neighbour_info;
            int i,j;
            NeighbourList_select(&n_info, &neighbours, &neighbour_info);
            simdbgverbose("stdout", "Checking Neighbours for slot collisions (our slot %u / hop %u): ", call TDMA.get_slot(), hop); NeighbourList_print(&n_info); simdbgverbose_clear("stdout", "\n");

            for(i=0; i<n_info.count; i++)
            {
                const NeighbourInfo* n_info_i = &n_info.info[i];
                // Check if there is a slot collision with a neighbour
                // Do not check for slot collisions with ourself
                if(n_info_i->slot == call TDMA.get_slot() && n_info_i->id != TOS_NODE_ID)
                {
                    simdbgverbose("stdout", "Found colliding slot from node %u, will evaluate if (%u || (%u && %u))\n",
                        n_info_i->id, (hop > n_info_i->hop), (hop == n_info_i->hop), (TOS_NODE_ID > n_info_i->id));

                    // To make sure only one node resolves the slot (rather than both)
                    // Have the node further from the sink resolve.
                    // If nodes have the same distance use the node id as a tie breaker.
                    if((hop > n_info_i->hop) || (hop == n_info_i->hop && TOS_NODE_ID > n_info_i->id))
                    {
                        call TDMA.set_slot(call TDMA.get_slot() - 1);

                        simdbgverbose("stdout", "Adjusted slot of current node to %u because node %u has slot %u.\n",
                            call TDMA.get_slot(), n_info_i->id, n_info_i->slot);
                        /*set_dissem_timer();*/
                    }
                }
            }

            simdbgverbose("stdout", "Checking for collisions between neighbours.\n");
            for(i=0; i < n_info.count; i++)
            {
                if(n_info.info[i].slot == BOT)
                {
                    /*set_dissem_timer();*/
                    /*simdbgverbose("stdout", "Detected node with slot=BOT, dissem_sending = TRUE\n");*/
                    break;
                }

                for(j=i+1; j < n_info.count; j++)
                {
                    if(n_info.info[i].slot == n_info.info[j].slot)
                    {
                        simdbgverbose("stdout", "Detected collision between %u and %u\n", n_info.info[i].id, n_info.info[j].id);
                        break;
                    }
                }
            }
            /*
             *simdbgverbose("stdout", "Checking for collisions between neighbours.\n");
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
        /*if(dissem_sending>0)*/
        /*{*/
            DissemMessage msg;
            msg.normal = normal;
            NeighbourList_select(&n_info, &neighbours, &(msg.N));

            simdbgverbose("stdout", "Sending dissem with: "); OnehopList_print(&(msg.N)); simdbgverbose_clear("stdout", "\n");

            send_Dissem_message(&msg, AM_BROADCAST_ADDR);
            /*dissem_sending--;*/
        /*}*/
        /*if(period_counter < get_pre_beacon_periods()) set_dissem_timer();*/
    }

	task void send_normal(void)
	{
        // This task may be delayed, such that it is scheduled when the slot is active,
        // but called after the slot is no longer active.
        // So it is important to check here if the slot is still active before sending.
        if (!call TDMA.is_slot_active())
        {
            return;
        }

		simdbgverbose("SourceBroadcasterC", "BroadcastTimer fired.\n");

		if (!(call MessageQueue.empty()))
		{
            NormalMessage* message = call MessageQueue.head();

            error_t send_result = send_Normal_message_ex(message, AM_BROADCAST_ADDR);
			if (send_result == SUCCESS)
			{
                NormalMessage* message2 = call MessageQueue.dequeue();
                assert(message == message2);
				call MessagePool.put(message);
			}
			else
			{
                ERROR_OCCURRED(ERROR_BROADCAST_FAILED,
                    "Send failed with code %u, not returning memory to pool so it will be tried again\n",
                    send_result);
                post send_normal();
			}

            //LOG_STDOUT(ERROR_UNKNOWN, "Sent Normal %"PRIu32" (%s)\n",
            //    message->sequence_number, call NodeType.to_string(call NodeType.get()));
		}
        else
        {
            EmptyNormalMessage msg;
            msg.sequence_number = call EmptyNormalSeqNos.next(TOS_NODE_ID);
            call EmptyNormalSeqNos.increment(TOS_NODE_ID);
            send_EmptyNormal_message(&msg, AM_BROADCAST_ADDR);
        }
	}

    void send_Normal_done(message_t* msg, error_t error)
    {
        // If our slot is currently active and there are more messages to be sent
        // then send them.
        if (call TDMA.is_slot_active() && !(call MessageQueue.empty()))
        {
            post send_normal();
        }
    }

    void MessageQueue_clear(void)
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
        assert(call MessageQueue.empty());
    }
    //Main Logic}}}

    //Timers.fired(){{{
    event bool TDMA.dissem_fired()
    {
        /*PRINTF0("%s: BeaconTimer fired.\n", sim_time_string());*/
        const uint32_t now = call LocalTime.get();
        METRIC_START_PERIOD();
        period_counter++;
        if(call NodeType.get() != SourceNode) MessageQueue_clear(); //XXX Dirty hack to stop other nodes sending stale messages
        if(call TDMA.get_slot() != BOT || period_counter < get_pre_beacon_periods())
        {
            call DissemTimerSender.startOneShotAt(now, random_interval(0, get_dissem_period()));
        }

        if(period_counter > get_pre_beacon_periods())
        {
            process_dissem();
            process_collision();
        }

        return TRUE;
    }

    event void TDMA.slot_started()
    {
        if(call TDMA.get_slot() != BOT && call NodeType.get() != SinkNode && period_counter > get_minimum_setup_periods())
        {
            post send_normal();
        }
    }

    event void TDMA.slot_finished()
    {
    }

    event void SourcePeriodModel.fired()
    {
        if(call TDMA.get_slot() != BOT && period_counter > get_minimum_setup_periods())
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
                    call MessagePool.put(message);
                    ERROR_OCCURRED(ERROR_QUEUE_FULL, "No queue space available for another Normal message.\n");
                }
                else
                {
                    call NormalSeqNos.increment(TOS_NODE_ID);
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
        /*simdbgverbose("stdout", "Received normal.\n");*/
		if (call NormalSeqNos.before_and_update(rcvd->source_id, rcvd->sequence_number))
		{
			NormalMessage* forwarding_message;

			METRIC_RCV_NORMAL(rcvd);

			forwarding_message = call MessagePool.get();
			if (forwarding_message != NULL)
			{
				*forwarding_message = *rcvd;
				forwarding_message->source_distance += 1;

				if (call MessageQueue.enqueue(forwarding_message) != SUCCESS)
				{
                    call MessagePool.put(forwarding_message);
					ERROR_OCCURRED(ERROR_QUEUE_FULL, "No queue space available for another Normal message.\n");
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
		if (call NormalSeqNos.before_and_update(rcvd->source_id, rcvd->sequence_number))
		{
			METRIC_RCV_NORMAL(rcvd);

            //LOG_STDOUT(ERROR_UNKNOWN, "Received Normal %"PRIu32"\n", rcvd->sequence_number);
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
        const NeighbourInfo* source;
        NeighbourList rcvdList;

        METRIC_RCV_DISSEM(rcvd);

        OnehopList_to_NeighbourList(&(rcvd->N), &rcvdList);
        source = NeighbourList_get(&rcvdList, source_addr);

        // Record that the sender is in our 1-hop neighbourhood
        IDList_add(&neighbours, source_addr);
        if(NeighbourList_get(&n_info, source_addr) == NULL)
        {
            NeighbourList_add(&n_info, source_addr, BOT, BOT);
        }

        if(rcvd->normal)
        {
            if(call TDMA.get_slot() == BOT && source->slot != BOT)
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
                        /*set_dissem_timer();*/
                        /*simdbgverbose("stdout", "### Slot information was different, dissem_sending = TRUE\n");*/
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
                if(call TDMA.get_slot() >= source->slot)
                {
                    /*call TDMA.set_slot(NeighbourList_get(&(rcvd->N), source_addr)->slot - (NeighbourList_get(&n_info, parent)->slot - NeighbourList_get(&(rcvd->N), parent)->slot));*/
                    call TDMA.set_slot(source->slot - (NeighbourList_get(&n_info, parent)->slot - source->slot));
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

        for(i = 0; i<rcvd->N.count; i++)
        {
            NeighbourList_add_info(&n_info, &rcvd->N.info[i]);
        }
    }


    RECEIVE_MESSAGE_BEGIN(Dissem, Receive)
        case SourceNode:
        case NormalNode: x_receive_Dissem(rcvd, source_addr); break;
        case SinkNode  : Sink_receive_Dissem(rcvd, source_addr); break;
    RECEIVE_MESSAGE_END(Dissem)

    void x_receive_EmptyNormal(const EmptyNormalMessage* const rcvd, am_addr_t source_addr)
    {
        if (call EmptyNormalSeqNos.before_and_update(source_addr, rcvd->sequence_number))
        {
            METRIC_RCV_EMPTYNORMAL(rcvd);
        }
    }

    RECEIVE_MESSAGE_BEGIN(EmptyNormal, Receive)
        case SourceNode:
        case NormalNode:
        case SinkNode:   x_receive_EmptyNormal(rcvd, source_addr); break;
    RECEIVE_MESSAGE_END(EmptyNormal)
}
