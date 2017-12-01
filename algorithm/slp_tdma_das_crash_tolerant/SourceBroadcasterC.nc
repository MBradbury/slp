#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "NormalMessage.h"
#include "DissemMessage.h"
#include "SearchMessage.h"
#include "ChangeMessage.h"
#include "EmptyNormalMessage.h"
/*#include "RepairMessage.h"*/
#include "CrashMessage.h"

#include "utils.h"

#include <Timer.h>
#include <TinyError.h>

#include <stdlib.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_DISSEM(msg) METRIC_RCV(Dissem, source_addr, source_addr, BOTTOM, 1)
#define METRIC_RCV_SEARCH(msg) METRIC_RCV(Search, source_addr, source_addr, BOTTOM, 1)
#define METRIC_RCV_CHANGE(msg) METRIC_RCV(Change, source_addr, source_addr, BOTTOM, 1)
#define METRIC_RCV_EMPTYNORMAL(msg) METRIC_RCV(EmptyNormal, source_addr, source_addr, BOTTOM, 1)
#define METRIC_RCV_REPAIR(msg) METRIC_RCV(Repair, source_addr, msg->source_id, BOTTOM, msg->distance + 1)
#define METRIC_RCV_CRASH(msg) METRIC_RCV(Crash, source_addr, source_addr, BOTTOM, 1)

#define BOT UINT16_MAX

#define PRINTF(node, ...) if(TOS_NODE_ID==node)simdbgverbose("stdout", __VA_ARGS__);
#define PRINTF0(...) PRINTF(0,__VA_ARGS__)

//TODO: Repair messages only sent once, not each period

//Distance search messages travel from sink
//Search + Change < Sink-Source Distance - 2

//Length of phantom route
/*#define PR_LENGTH 10 //Half sink-source distance/safety period (which is 5 for 11x11)*/
/*#define SEARCH_PERIOD_COUNT 24*/

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

    uses interface AMSend as SearchSend;
    uses interface Receive as SearchReceive;

    uses interface AMSend as ChangeSend;
    uses interface Receive as ChangeReceive;

    uses interface AMSend as EmptyNormalSend;
    uses interface Receive as EmptyNormalReceive;

    /*uses interface AMSend as RepairSend;*/
    /*uses interface Receive as RepairReceive;*/

    uses interface AMSend as CrashSend;
    uses interface Receive as CrashReceive;

    uses interface MetricLogging;
	uses interface MetricHelpers;

    uses interface TDMA;

    uses interface NodeType;
    uses interface MessageType;
    uses interface ObjectDetector;
    uses interface SourcePeriodModel;

    uses interface SequenceNumbers as NormalSeqNos;

    uses interface FaultModel;
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

    bool start = TRUE;
    bool normal = TRUE;
    IDList from;

    uint32_t period_counter = 0;
    bool start_node = FALSE;
    uint32_t redir_length = 0;

    //The position of the node along the critical path
    uint16_t path_order = BOT;
    //Keep track of the two connected nodes on the critical path
    uint16_t path_child = BOT;
    uint16_t path_parent = BOT;

#define PATH_STILL_ALIVE 4
    /*uint8_t path_child_alive = PATH_STILL_ALIVE;*/
    /*uint8_t path_parent_alive = PATH_STILL_ALIVE;*/

    /*bool repair_sending = FALSE;*/
    /*RepairMessage repair_message;*/

    IDList crash_suspects;
    bool active = FALSE;

    uint16_t path_child_wait = BOT;

    enum
    {
        SourceNode,
        SinkNode,
        NormalNode,
        SearchNode,
        ChangeNode,
    };

    enum
    {
        UnknownFaultPoint = 0,
        PathFaultPoint,
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

    uint32_t get_search_dist()
    {
        return SEARCH_DIST;
    }

    uint32_t get_search_period_count()
    {
        return get_minimum_setup_periods() - 2;
    }

    uint32_t get_change_period_count()
    {
        return get_minimum_setup_periods() - 1;
    }

    uint32_t get_change_length()
    {
        return CHANGE_LENGTH;
    }

    uint32_t get_normal_start_period()
    {
        return get_minimum_setup_periods() + PATH_STILL_ALIVE + 2;
    }
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

    void set_path_parent(uint16_t new_parent) {
        path_parent = new_parent;
        simdbg("stdout", "Set path parent to %" PRIu16 " (slot=%u)\n", path_parent, call TDMA.get_slot());
    }

    void set_path_child(uint16_t new_child) {
        path_child = new_child;
        simdbg("stdout", "Set path child to %" PRIu16 " (slot=%u)\n", path_child, call TDMA.get_slot());
    }

    void set_path_order(uint16_t new_order) {
        path_order = new_order;
        simdbg("stdout", "Set path order to %" PRIu16 " (slot=%u)\n", path_order, call TDMA.get_slot());
    }
    //###################}}}

    //Startup Events
    event void Boot.booted()
    {
        neighbours = IDList_new();
        potential_parents = IDList_new();
        others = OtherList_new();
        n_info = NeighbourList_new();
        children = IDList_new();
        from = IDList_new();
        crash_suspects = IDList_new();

        METRIC_BOOT();

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

        call FaultModel.register_pair(PathFaultPoint, "PathFaultPoint");

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
    USE_MESSAGE_WITH_CALLBACK_NO_EXTRA_TO_SEND(Search);
    USE_MESSAGE_WITH_CALLBACK_NO_EXTRA_TO_SEND(Change);
    USE_MESSAGE_NO_EXTRA_TO_SEND(EmptyNormal);
    /*USE_MESSAGE_NO_EXTRA_TO_SEND(Repair);*/
    USE_MESSAGE_NO_EXTRA_TO_SEND(Crash);

    void init(void)
    {
        if (call NodeType.get() == SinkNode)
        {
            parent = AM_BROADCAST_ADDR;
            set_hop(0);
            call TDMA.set_slot(get_tdma_num_slots());

            start = FALSE;
            active = TRUE;
        }
        else
        {
            set_hop(BOT);
            call TDMA.set_slot(BOT);
        }

        IDList_add(&neighbours, TOS_NODE_ID);
    }

    void process_dissem(void)
    {
        int i;
        if(call TDMA.get_slot() == BOT)
        {
            const NeighbourInfo* parent_info = NeighbourList_info_for_min_hop(&n_info, &potential_parents);
            OtherInfo* other_info;

            if (parent_info == NULL) {
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
            active = TRUE;

            /*simdbgverbose("stdout", "OtherList: "); IDList_print(&(other_info->N)); simdbgverbose_clear("stdout", "\n");*/

            simdbgverbose("stdout", "Updating parent to %u, slot to %u and hop to %u.\n", parent, call TDMA.get_slot(), hop);

            {
                OnehopList onehop;
                NeighbourList_select(&n_info, &neighbours, &onehop);
                for(i = 0; i < onehop.count; i++)
                {
                    if(onehop.info[i].hop == BOT)
                    {
                        IDList_add(&children, onehop.info[i].id);
                    }
                }
                /*simdbgverbose("stdout", "Added children to list: "); IDList_print(&children); simdbgverbose_clear("stdout", "\n");*/
            }
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
                    }
                }
            }

            simdbgverbose("stdout", "Checking for collisions between neighbours.\n");
            for(i=0; i < n_info.count; i++)
            {
                if(n_info.info[i].slot == BOT)
                {
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

            //Check to see if DAS has been broken
            if(call NodeType.get() != SinkNode){
                bool das = FALSE;
                for(i=0; i < potential_parents.count; i++)
                {
                    for(j=i+1; j < neighbour_info.count; j++)
                    {
                        if(potential_parents.ids[i] == neighbour_info.info[j].id)
                        {
                            if(neighbour_info.info[j].slot > call TDMA.get_slot()) das = TRUE;
                        }
                    }
                }
                if(!das) simdbgverbose("DAS-State", "DAS is 0\n");
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
        DissemMessage msg;
        msg.normal = normal;
        msg.parent = parent;
        NeighbourList_select(&n_info, &neighbours, &(msg.N));

        simdbgverbose("stdout", "Sending dissem with: "); OnehopList_print(&(msg.N)); simdbgverbose_clear("stdout", "\n");

        send_Dissem_message(&msg, AM_BROADCAST_ADDR);
        /*normal = TRUE; //TODO: Testing this line*/
    }

    void send_search_init()
    {
        if(call NodeType.get() == SinkNode)
        {
            int i;
            SearchMessage msg;
            OnehopList child_list;
            uint16_t min_slot = BOT;
            msg.dist = get_search_dist() - 1;
            msg.a_node = BOT;
            set_path_order(0);
            msg.path_order = 0;
            assert(children.count != 0);
            NeighbourList_select(&n_info, &children, &child_list);
            min_slot = OnehopList_min_slot(&child_list);
            for(i=0; i<children.count; i++) {
                NeighbourInfo* child = NeighbourList_get(&n_info, children.ids[i]);
                if(child->slot == min_slot)
                {
                    msg.a_node = child->id;
                }
            }
            send_Search_message(&msg, AM_BROADCAST_ADDR);
            simdbgverbose("stdout", "Sent search message to %u\n", msg.a_node);

            set_path_parent(BOT);
            set_path_child(msg.a_node);
        }
    }

    void send_change_init()
    {
        if(start_node)
        {
            int i;
            ChangeMessage msg;
            OnehopList onehop;
            /*IDList npar = IDList_minus_parent(&potential_parents, parent);*/
            IDList npar = IDList_minus_parent(&neighbours, parent);
            npar = IDList_minus_parent(&npar, TOS_NODE_ID);
            for(i = 0; i < from.count; i++)
            {
                npar = IDList_minus_parent(&npar, from.ids[i]);
            }
            simdbgverbose("stdout", "CHANGE HAS BEGUN\n");
            start_node = FALSE;
            NeighbourList_select(&n_info, &neighbours, &onehop);
            msg.a_node = choose(&npar);
            msg.n_slot = OnehopList_min_slot(&onehop);
            msg.len_d = redir_length - 1;
            msg.path_order = path_order;
            send_Change_message(&msg, AM_BROADCAST_ADDR);
            call NodeType.set(ChangeNode);
            simdbgverbose("a_node was %u\n", msg.a_node);

            set_path_child(msg.a_node);
        }
    }

    /*void send_repair_init()*/
    /*{*/
        /*repair_message.source_id = TOS_NODE_ID;*/
        /*repair_message.source_path_order = path_order;*/
        /*repair_message.distance = 1;*/
        /*repair_message.path[0] = TOS_NODE_ID;*/
        /*send_Repair_message(&repair_message, AM_BROADCAST_ADDR);*/
        /*repair_sending = TRUE;*/
    /*}*/

    void send_crash_init()
    {
        CrashMessage msg;
        send_Crash_message(&msg, AM_BROADCAST_ADDR);
    }

    task void send_normal(void)
    {
        NormalMessage* message;

        // This task may be delayed, such that it is scheduled when the slot is active,
        // but called after the slot is no longer active.
        // So it is important to check here if the slot is still active before sending.
        if (!call TDMA.is_slot_active())
        {
            return;
        }

        simdbgverbose("SourceBroadcasterC", "BroadcastTimer fired.\n");

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
                simdbgerrorverbose("stdout", "send failed with code %u, not returning memory to pool so it will be tried again\n", send_result);
            }
        }
        else
        {
            EmptyNormalMessage msg;
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

    void send_Search_done(message_t* msg, error_t error)
    {
        if(!call NodeType.is_node_sink() && period_counter == get_search_period_count())
        /*if(path_order == 3 && period_counter == get_search_period_count())*/
        {
            call FaultModel.fault_point(PathFaultPoint);
        }
    }

    void send_Change_done(message_t* msg, error_t error)
    {
        //Don't activate fault point if we are repairing the path
        if(period_counter == get_change_period_count())
        {
            call FaultModel.fault_point(PathFaultPoint);
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

    //Record the message reception to remove from crash suspects
    inline void record_rcv(am_addr_t source_addr)
    {
        if(IDList_indexOf(&crash_suspects, source_addr) != BOT) {
            IDList_remove(&crash_suspects, source_addr);
        }
    }

    void reset_node() {
        call TDMA.set_slot(BOT);
        set_hop(BOT);
        parent = BOT;
        {
            int i;
            for(i = 0; i < n_info.count; i++) {
                n_info.info[i].slot = BOT;
                n_info.info[i].hop = BOT;
            }
        }
    }

    void check_crashes()
    {
        //Remove crashed nodes from all data structures
        {
            int i;
            for(i = 0; i < crash_suspects.count; i++)
            {
                if(NeighbourList_get(&n_info, crash_suspects.ids[i])->slot != BOT)
                {
                    IDList_remove(&neighbours, crash_suspects.ids[i]);
                    IDList_remove(&potential_parents, crash_suspects.ids[i]);
                    IDList_remove(&children, crash_suspects.ids[i]);
                    IDList_remove(&from, crash_suspects.ids[i]);
                    NeighbourList_remove(&n_info, crash_suspects.ids[i]);
                    OtherList_remove_all(&others, crash_suspects.ids[i]);
                }
            }
        }

        //Check if parent has crashed
        if(IDList_indexOf(&crash_suspects, parent) != BOT)
        {
            simdbg("stdout", "Parent crashed\n");
            if(potential_parents.count > 0)
            {
                OtherInfo* other_info;
                NeighbourInfo* parent_info = NeighbourList_get(&n_info, potential_parents.ids[0]);
                if(parent_info == NULL) {
                    reset_node();
                    send_crash_init();
                    return;
                }
                other_info = OtherList_get(&others, parent_info->id);
                if(other_info == NULL) {
                    reset_node();
                    send_crash_init();
                    return;
                }
                parent = parent_info->id;
                set_hop(parent_info->hop + 1);
                call TDMA.set_slot(parent_info->slot - rank(&(other_info->N), TOS_NODE_ID) - get_assignment_interval() - 1);
            }
            else
            {
                reset_node();
            }
            send_crash_init();
        }

        //Check if path child has crashed
        if(path_child != BOT && IDList_indexOf(&crash_suspects, path_child) != BOT) {
            simdbg("stdout", "Path child crashed\n");
            path_child_wait = PATH_STILL_ALIVE;
        }

        if(path_child_wait != BOT) path_child_wait--;

        /*if(path_child != BOT && IDList_indexOf(&crash_suspects, path_child) != BOT)*/
        if(path_child_wait == 0)
        {
            path_child_wait = BOT;
            simdbg("stdout", "Starting repair process...\n");
            if(path_order < get_search_dist()) { //Send search
                if(children.count != 0) {
                    int i;
                    SearchMessage msg;
                    OnehopList child_list;
                    uint16_t min_slot = BOT;
                    msg.dist = get_search_dist() - path_order - 1;
                    msg.a_node = BOT;
                    msg.path_order = path_order;
                    /*assert(children.count != 0);*/
                    NeighbourList_select(&n_info, &children, &child_list);
                    min_slot = OnehopList_min_slot(&child_list);
                    for(i=0; i<children.count; i++) {
                        NeighbourInfo* child = NeighbourList_get(&n_info, children.ids[i]);
                        if(child->slot == min_slot)
                        {
                            msg.a_node = child->id;
                        }
                    }
                    send_Search_message(&msg, AM_BROADCAST_ADDR);
                    simdbgverbose("stdout", "Sent search message to %u\n", msg.a_node);

                    set_path_child(msg.a_node);
                }
                else {
                    simdbg("stdout", "Had no children\n");
                }
            }
            else { //Send change
                int i;
                ChangeMessage msg;
                OnehopList onehop;
                /*IDList npar = IDList_minus_parent(&potential_parents, parent);*/
                IDList npar = IDList_minus_parent(&neighbours, parent);
                npar = IDList_minus_parent(&npar, TOS_NODE_ID);
                for(i = 0; i < from.count; i++)
                {
                    npar = IDList_minus_parent(&npar, from.ids[i]);
                }
                simdbgverbose("stdout", "CHANGE HAS BEGUN\n");
                start_node = FALSE;
                NeighbourList_select(&n_info, &neighbours, &onehop);
                msg.a_node = choose(&npar);
                msg.n_slot = OnehopList_min_slot(&onehop);
                msg.len_d = get_change_length() + get_search_dist() - path_order- 1;
                msg.path_order = path_order;
                send_Change_message(&msg, AM_BROADCAST_ADDR);
                /*call NodeType.set(ChangeNode);*/
                simdbgverbose("a_node was %u\n", msg.a_node);

                set_path_child(msg.a_node);
            }
        }

        //Required as if path recreated from search messages, nothing will start the change process
        if(start_node) send_change_init();

        //Reset crash_suspects
        crash_suspects = IDList_minus_parent(&neighbours, TOS_NODE_ID);
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
        if(period_counter == get_search_period_count())
        {
            send_search_init();
            return FALSE;
        }
        else if(period_counter == get_change_period_count())
        {
            send_change_init();
            return FALSE;
        }
        /*if(call TDMA.get_slot() != BOT || period_counter < get_pre_beacon_periods())*/
        if(active || period_counter < get_pre_beacon_periods())
        {
            check_crashes();
            call DissemTimerSender.startOneShotAt(now, (uint32_t)(get_dissem_period() * random_float()));
        }

        if(period_counter > get_pre_beacon_periods())
        {
            process_dissem();
            process_collision();
        }

        //TODO The node with no child at the end of the path might suffer from this
        //Repair broken path
        /*if(call NodeType.get() == SinkNode || call NodeType.get() == SearchNode || call NodeType.get() == ChangeNode) {*/
        /*if(path_child != BOT) {*/
            /*path_child_alive = (path_child_alive==0) ? 0 : path_child_alive - 1;*/
            /*if(path_child_alive == 0) {*/
                /*[>start_node = TRUE;<]*/
                /*[>send_change_init();<]*/
            /*}*/
        /*}*/
        /*if(call NodeType.get() == SearchNode || call NodeType.get() == ChangeNode) {*/
            /*path_parent_alive--;*/
            /*if(path_parent_alive <= 0) {*/
                /*[>simdbg("stdout", "Sending path repair... (slot=%u)\n", call TDMA.get_slot());<]*/
                /*[>send_repair_init();<]*/
            /*}*/
        /*}*/

        /*if(repair_sending) {*/
            /*send_Repair_message(&repair_message, AM_BROADCAST_ADDR);*/
        /*}*/

        return TRUE;
    }

    event void TDMA.slot_started()
    {
        if(call TDMA.get_slot() != BOT && call NodeType.get() != SinkNode && period_counter > get_normal_start_period())
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
        record_rcv(source_addr);
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
        simdbgverbose("stdout", "SINK RECEIVED NORMAL.\n");
        record_rcv(source_addr);
        if (call NormalSeqNos.before(TOS_NODE_ID, rcvd->sequence_number))
        {
            call NormalSeqNos.update(TOS_NODE_ID, rcvd->sequence_number);

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

        record_rcv(source_addr);
        METRIC_RCV_DISSEM(rcvd);

        OnehopList_to_NeighbourList(&(rcvd->N), &rcvdList);
        source = NeighbourList_get(&rcvdList, source_addr);

        // Record that the sender is in our 1-hop neighbourhood
        IDList_add(&neighbours, source_addr);
        if(NeighbourList_get(&n_info, source_addr) == NULL)
        {
            NeighbourList_add(&n_info, source_addr, BOT, BOT);
        }

        for(i = 0; i<rcvd->N.count; i++)
        {
            if(rcvd->N.info[i].slot != BOT && rcvd->N.info[i].id != TOS_NODE_ID) //XXX Collision fix is here
            {
                NeighbourInfo* oldinfo = NeighbourList_get(&n_info, rcvd->N.info[i].id);
                if(oldinfo == NULL || (rcvd->N.info[i].slot != oldinfo->slot && rcvd->N.info[i].slot < oldinfo->slot)) //XXX Stops stale data?
                {
                    NeighbourList_add_info(&n_info, &rcvd->N.info[i]);
                }
            }
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
        }
        else
        {
            if(parent == source_addr)
            {
                if(call TDMA.get_slot() >= source->slot)
                {
                    OnehopList p_parents;
                    IDList p_list = IDList_minus_parent(&potential_parents, parent);
                    NeighbourList_select(&n_info, &p_list, &p_parents);
                    for(i = 0; i < p_parents.count; i++)
                    {
                        if(p_parents.info[i].slot < call TDMA.get_slot())
                        {
                            /*call TDMA.set_slot( source->slot - (NeighbourList_get(&n_info, parent)->slot - source->slot) );*/
                            call TDMA.set_slot( source->slot - 1 ); //TODO: Testing
                            normal = FALSE;
                            break;
                        }
                    }
                }
                NeighbourList_add_info(&n_info, source);
            }
        }

        //Update the still alive count of the parent/child in the path
        /*if(source_addr == path_parent) {*/
            /*path_parent_alive = PATH_STILL_ALIVE;*/
        /*}*/
        /*else if(source_addr == path_child) {*/
            /*path_child_alive = PATH_STILL_ALIVE;*/
        /*}*/

        /*if(call TDMA.get_slot() != BOT) //TODO Why the if slot?*/
        /*{*/
            /*IDList_remove(&crash_suspects, source_addr);*/
        /*}*/
    }

    void Sink_receive_Dissem(const DissemMessage* const rcvd, am_addr_t source_addr)
    {
        int i;

        record_rcv(source_addr);
        METRIC_RCV_DISSEM(rcvd);

        IDList_add(&neighbours, source_addr);

        if(rcvd->parent == TOS_NODE_ID)
        {
            IDList_add(&children, source_addr);
            /*simdbgverbose("stdout", "Added child to list: "); IDList_print(&children); simdbgverbose_clear("stdout", "\n");*/
        }

        for(i = 0; i<rcvd->N.count; i++)
        {
            NeighbourList_add_info(&n_info, &rcvd->N.info[i]);
        }

        if(call TDMA.get_slot() != BOT)
        {
            IDList_remove(&crash_suspects, source_addr);
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
        IDList_add(&from, source_addr); //TODO: Testing
        record_rcv(source_addr);
        METRIC_RCV_SEARCH(rcvd);
        if(rcvd->a_node != TOS_NODE_ID) return;
        simdbgverbose("stdout", "Received search\n");

        set_path_parent(source_addr);
        set_path_order(rcvd->path_order + 1);

        if((rcvd->dist == 0 && npar.count != 0))
        {
            start_node = TRUE;
            redir_length = get_change_length();
            simdbgverbose("stdout", "Search messages ended\n");
        }
        else if(rcvd->dist == 0 && npar.count == 0)
        {
            SearchMessage msg;
            msg.dist = rcvd->dist;
            msg.path_order = rcvd->path_order + 1;
            if(children.count != 0)
            {
                msg.a_node = choose(&children);
            }
            else
            {
                IDList n = IDList_minus_parent(&neighbours, parent);
                n = IDList_minus_parent(&n, TOS_NODE_ID);
                msg.a_node = choose(&n);
            }
            send_Search_message(&msg, AM_BROADCAST_ADDR);
            simdbgverbose("stdout", "Sent search message again to %u\n", msg.a_node);
            call NodeType.set(SearchNode);

            set_path_child(msg.a_node);
        }
        else if(rcvd->dist > 0)
        {
            int i;
            SearchMessage msg;
            OnehopList child_list;
            uint16_t min_slot = BOT;
            NeighbourList_select(&n_info, &children, &child_list);
            min_slot = OnehopList_min_slot(&child_list);
            msg.dist = (rcvd->dist-1<0) ? 0 : rcvd->dist - 1;
            msg.path_order = rcvd->path_order + 1;
            msg.a_node = BOT;
            for(i=0; i<children.count; i++) {
                NeighbourInfo* child = NeighbourList_get(&n_info, children.ids[i]);
                if(child->slot == min_slot)
                {
                    msg.a_node = child->id;
                }
            }
            send_Search_message(&msg, AM_BROADCAST_ADDR);
            simdbgverbose("stdout", "Sent search message again to %u\n", msg.a_node);
            call NodeType.set(SearchNode);

            set_path_child(msg.a_node);
        }
    }

    RECEIVE_MESSAGE_BEGIN(Search, Receive)
        case SourceNode: break;
        case SearchNode:
        case ChangeNode:
        case NormalNode: Normal_receive_Search(rcvd, source_addr); break;
        case SinkNode:   break;
    RECEIVE_MESSAGE_END(Search)

    void Normal_receive_Change(const ChangeMessage* const rcvd, am_addr_t source_addr)
    {
        int i;
        IDList npar;
        record_rcv(source_addr);
        METRIC_RCV_CHANGE(rcvd);
        if(rcvd->a_node != TOS_NODE_ID) return;
        /*npar = IDList_minus_parent(&potential_parents, parent);*/
        npar = IDList_minus_parent(&neighbours, parent);
        npar = IDList_minus_parent(&npar, source_addr); //TODO: Check if this is necessary
        npar = IDList_minus_parent(&npar, TOS_NODE_ID);

        set_path_parent(source_addr);
        set_path_order(rcvd->path_order + 1);
        /*repair_sending = FALSE;*/

        for(i = 0; i < from.count; i++)
        {
            npar = IDList_minus_parent(&npar, from.ids[i]);
        }
        if(rcvd->len_d > 0 && npar.count != 0)
        {
            ChangeMessage msg;
            OnehopList onehop;
            simdbgverbose("stdout", "Received change\n");
            call TDMA.set_slot(rcvd->n_slot - 1);
            //NeighbourList_add(&n_info, TOS_NODE_ID, hop, slot); //Update own information before processing
            NeighbourList_get(&n_info, source_addr)->slot = rcvd->n_slot; //Update source_addr node with new slot information
            NeighbourList_select(&n_info, &neighbours, &onehop);
            msg.n_slot = OnehopList_min_slot(&onehop);
            msg.a_node = choose(&npar);
            msg.len_d = rcvd->len_d - 1;
            msg.path_order = rcvd->path_order + 1;
            send_Change_message(&msg, AM_BROADCAST_ADDR);
            call NodeType.set(ChangeNode);
            simdbgverbose("stdout", "Next a_node is %u\n", msg.a_node);

            set_path_child(msg.a_node);
        }
        else if(rcvd->len_d == 0 && npar.count != 0)
        {
            normal = FALSE;
            call TDMA.set_slot(rcvd->n_slot - 1);
            //NeighbourList_add(&n_info, TOS_NODE_ID, hop, slot);
            simdbgverbose("stdout", "Change messages ended\n");
            call NodeType.set(ChangeNode);
        }
        //If this is a repair change message and you have a child
        /*else if(rcvd->len_d == BOTTOM && path_child != BOT)*/
        /*{*/
            /*ChangeMessage msg;*/
            /*OnehopList onehop;*/
            /*call TDMA.set_slot(rcvd->n_slot - 1);*/
            /*//If necessary and possible, change parent*/
            /*[>if(path_child == parent && npar.count != 0) {<]*/
                /*[>parent = npar.ids[0];<]*/
            /*[>}<]*/
            /*NeighbourList_get(&n_info, source_addr)->slot = rcvd->n_slot; //Update source_addr node with new slot information*/
            /*NeighbourList_select(&n_info, &neighbours, &onehop);*/
            /*msg.n_slot = OnehopList_min_slot(&onehop);*/
            /*msg.a_node = path_child;*/
            /*msg.len_d = BOTTOM;*/
            /*msg.path_order = rcvd->path_order + 1;*/
            /*send_Change_message(&msg, AM_BROADCAST_ADDR);*/
            /*call NodeType.set(ChangeNode);*/
            /*simdbg("stdout", "ID = %u (slot = %u) became new change\n", TOS_NODE_ID, call TDMA.get_slot());*/
        /*}*/
        simdbgverbose("stdout", "a_node=%u, len_d=%u, n_slot=%u\n", rcvd->a_node, rcvd->len_d, rcvd->n_slot);
    }

    //TODO Change receive change (set new path order and slot)?
    RECEIVE_MESSAGE_BEGIN(Change, Receive)
        case SourceNode: break;
        case SearchNode:
        case ChangeNode:
        case NormalNode: Normal_receive_Change(rcvd, source_addr); break;
        case SinkNode:   break;
    RECEIVE_MESSAGE_END(Change)

    void x_receive_EmptyNormal(const EmptyNormalMessage* const rcvd, am_addr_t source_addr)
    {
        record_rcv(source_addr);
        METRIC_RCV_EMPTYNORMAL(rcvd);
    }

    RECEIVE_MESSAGE_BEGIN(EmptyNormal, Receive)
        case SourceNode:
        case SearchNode:
        case ChangeNode:
        case NormalNode:
        case SinkNode:   x_receive_EmptyNormal(rcvd, source_addr); break;
    RECEIVE_MESSAGE_END(EmptyNormal)

    /*void Normal_receive_Repair(const RepairMessage* const rcvd, am_addr_t source_addr)*/
    /*{*/
        /*int i;*/

        /*[>simdbg("stdout", "NormalNode received repair message.\n");<]*/
        /*record_rcv(source_addr);*/
        /*METRIC_RCV_REPAIR(rcvd);*/

        /*//Stop if the maximum range of the message has been reached*/
        /*//TODO Timeout path_child validity?*/
        /*if(rcvd->distance + 1 == MAX_REPAIR_PATH_LENGTH || path_child != BOT) return;*/

        /*//TODO: Compare distance of new child to old one (done?)*/
        /*[>path_child = rcvd->path[rcvd->distance - 1];<]*/
        /*[>set_path_child(rcvd->path[rcvd->distance - 1]);<]*/
        /*set_path_child(source_addr);*/

        /*repair_message.source_id = rcvd->source_id;*/
        /*repair_message.source_path_order = rcvd->source_path_order;*/
        /*repair_message.distance = rcvd->distance + 1;*/
        /*for(i = 0; i < rcvd->distance; i++)*/
        /*{*/
            /*repair_message.path[i] = rcvd->path[i];*/
        /*}*/
        /*repair_message.path[rcvd->distance] = TOS_NODE_ID;*/
        /*simdbg("stdout", "Sending on repair message (slot=%u)\n", call TDMA.get_slot());*/
        /*send_Repair_message(&repair_message, AM_BROADCAST_ADDR);*/
        /*repair_sending = TRUE;*/
    /*}*/

    /*void Path_receive_Repair(const RepairMessage* const rcvd, am_addr_t source_addr)*/
    /*{*/
        /*ChangeMessage msg;*/
        /*OnehopList onehop;*/
        /*record_rcv(source_addr);*/
        /*METRIC_RCV_REPAIR(rcvd);*/
        /*//If the message was sent from a node before you in the path*/
        /*//or if you believe your child is still alive, ignore it*/
        /*simdbg("stdout", "%s received repair message.\n", call NodeType.current_to_string());*/
        /*simdbg("stdout", "path_order=%u > source_order=%u || path_child_alive=%u > 0\n", path_order, rcvd->source_path_order, path_child_alive);*/
        /*if(path_order > rcvd->source_path_order || path_child_alive > 0) return; //TODO: Check the inequality is the correct way round*/
        /*simdbg("stdout", "%s processing repair message.\n", call NodeType.current_to_string());*/
        /*[>set_path_child(rcvd->path[rcvd->distance - 1]);<]*/
        /*set_path_child(source_addr);*/
        /*NeighbourList_select(&n_info, &neighbours, &onehop);*/
        /*//TODO Set path_child slot in n_info*/
        /*msg.n_slot = OnehopList_min_slot(&onehop);*/
        /*msg.len_d = BOTTOM;*/
        /*msg.a_node = path_child;*/
        /*msg.path_order = path_order;*/
        /*send_Change_message(&msg, AM_BROADCAST_ADDR);*/
    /*}*/

    /*RECEIVE_MESSAGE_BEGIN(Repair, Receive)*/
        /*case SourceNode:    break;*/
        /*case SearchNode:*/
        /*case ChangeNode:*/
        /*case SinkNode:      Path_receive_Repair(rcvd, source_addr); break;*/
        /*case NormalNode:    Normal_receive_Repair(rcvd, source_addr); break;*/
    /*RECEIVE_MESSAGE_END(Repair)*/

    void x_receive_Crash(const CrashMessage* const rcvd, am_addr_t source_addr)
    {
        record_rcv(source_addr);
        METRIC_RCV_CRASH(rcvd);
        if(parent == source_addr)
        {
            CrashMessage msg;
            if(potential_parents.count > 0)
            {
                OtherInfo* other_info;
                NeighbourInfo* parent_info = NeighbourList_get(&n_info, potential_parents.ids[0]);
                if(parent_info == NULL) {
                    reset_node();
                    send_Crash_message(&msg, AM_BROADCAST_ADDR);
                    return;
                }
                other_info = OtherList_get(&others, parent_info->id);
                if(other_info == NULL) {
                    reset_node();
                    send_Crash_message(&msg, AM_BROADCAST_ADDR);
                    return;
                }
                parent = parent_info->id;
                set_hop(parent_info->hop + 1);
                call TDMA.set_slot(parent_info->slot - rank(&(other_info->N), TOS_NODE_ID) - get_assignment_interval() - 1);
            }
            else
            {
                reset_node();
            }
            send_Crash_message(&msg, AM_BROADCAST_ADDR);
        }
    }

    RECEIVE_MESSAGE_BEGIN(Crash, Receive)
        case SinkNode:      break;
        case SourceNode:
        case NormalNode:
        case SearchNode:
        case ChangeNode:    x_receive_Crash(rcvd, source_addr); break;
    RECEIVE_MESSAGE_END(Crash)
}
