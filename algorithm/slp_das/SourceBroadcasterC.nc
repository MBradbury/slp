#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "NormalMessage.h"
#include "DummyNormalMessage.h"
#include "BeaconMessage.h"
#include "DissemMessage.h"

#include "utils.h"

#include <Timer.h>
#include <TinyError.h>

#include <assert.h>
#include <stdlib.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_DUMMYNORMAL(msg) METRIC_RCV(DummyNormal, source_addr, source_addr, BOTTOM, 1)

#define BOT UINT16_MAX

#define BEACON_PERIOD_MS 500
#define SLOT_PERIOD_MS 100
#define INIT_PERIOD_MS 2000
/*#define DISSEM_PERIOD_MS 5000*/

#define TDMA_NUM_SLOTS 50
#define LOOP_LENGTH 4

#define PRINTF(node, ...) if(TOS_NODE_ID==node)simdbg("stdout", __VA_ARGS__);
#define PRINTF0(...) PRINTF(0,__VA_ARGS__)


module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;

    uses interface Timer<TMilli> as DissemTimer;
    uses interface Timer<TMilli> as InitTimer;
	uses interface Timer<TMilli> as EnqueueNormalTimer;
    uses interface Timer<TMilli> as BeaconTimer;
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

	uses interface AMSend as DummyNormalSend;
	uses interface Receive as DummyNormalReceive;

    /*uses interface AMSend as BeaconSend;*/
    /*uses interface Receive as BeaconReceive;*/

    uses interface AMSend as DissemSend;
    uses interface Receive as DissemReceive;

	uses interface ObjectDetector;
	uses interface SourcePeriodModel;

	uses interface SequenceNumbers as NormalSeqNos;
}

implementation
{
    //Initialisation variables{{{
    IDList neighbours;
    IDList potential_parents;
    OtherList others;
    NeighbourList n_info;
    NeighbourList onehop;

    uint16_t hop = BOT;
    uint16_t parent = BOT;
    uint16_t slot = BOT;

    bool start = TRUE;
    bool slot_active = FALSE;

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

	uint32_t get_broadcast_period()
	{
		return BROADCAST_PERIOD_MS;
	}

    uint32_t get_beacon_period()
    {
        return BEACON_PERIOD_MS;
    }

    uint32_t get_slot_period()
    {
        return SLOT_PERIOD_MS;
    }

    uint32_t get_init_period()
    {
        return INIT_PERIOD_MS;
    }

    /*uint32_t get_dissem_period()*/
    /*{*/
        /*return DISSEM_PERIOD_MS;*/
    /*}*/

    uint32_t get_tdma_num_slots()
    {
        return TDMA_NUM_SLOTS;
    }

    uint32_t get_loop_length()
    {
        return LOOP_LENGTH;
    }
    //###################}}}

    //Startup Events{{{
	event void Boot.booted()
	{
        neighbours = IDList_new();
        potential_parents = IDList_new();
        others = OtherList_new();
        n_info = NeighbourList_new();
        onehop = NeighbourList_new();

		simdbgverbose("Boot", "%s: Application booted.\n", sim_time_string());

		if (TOS_NODE_ID == SINK_NODE_ID)
		{
			type = SinkNode;
			simdbg("Node-Change-Notification", "The node has become a Sink\n");
		}

		call RadioControl.start();
	}

    void init();
    void send_beacon();
	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			simdbgverbose("SourceBroadcasterC", "%s: RadioControl started.\n", sim_time_string());

            init();
            call InitTimer.startOneShot(get_init_period());
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
	USE_MESSAGE(DummyNormal);
    /*USE_MESSAGE(Beacon);*/
    USE_MESSAGE(Dissem);

    void init()
    {
        if(type == SinkNode)
        {
            int i;
            for(i=0; i<neighbours.count; i++)
            {
                NeighbourList_add(&n_info, neighbours.ids[i], BOT, BOT);
            }
            start = FALSE;
            hop = 0;
            parent = BOT;
            slot = get_tdma_num_slots(); //Delta
            NeighbourList_add(&n_info, TOS_NODE_ID, 0, get_tdma_num_slots()); //Delta
            NeighbourList_add(&onehop, TOS_NODE_ID, 0, get_tdma_num_slots());
        }
        else
        {
            NeighbourList_add(&n_info, TOS_NODE_ID, BOT, BOT);
            NeighbourList_add(&onehop, TOS_NODE_ID, BOT, BOT);
        }
    }


    void process_dissem()
    {
        int i;
        /*simdbg("stdout", "Processing...\n");*/
        if(slot == BOT && type != SinkNode)
        {
            NeighbourInfo* info = NeighbourList_min_h(&n_info, &potential_parents);
            OtherInfo* other_info;
            if (info == NULL) {
                /*simdbg("stdout", "Info was NULL.\n");*/
                return;
            }
            else
            {
                simdbg("stdout", "Info was: ID=%u, hop=%u, slot=%u.\n", info->id, info->hop, info->slot);
            }
            other_info = OtherList_get(&others, info->id);
            if(other_info == NULL) {
                simdbg("stdout", "Other info was NULL.\n");
                return;
            }
            hop = info->hop + 1;
            parent = info->id;
            simdbg("stdout", "Chosen parent %u.\n", parent);
            slot = info->slot - rank(&(other_info->N), TOS_NODE_ID) - get_loop_length() - 1;
            simdbg("stdout", "Chosen slot %u.\n", slot);
            NeighbourList_add(&n_info, TOS_NODE_ID, hop, slot);
            NeighbourList_add(&onehop, TOS_NODE_ID, hop, slot);
        }

        for(i=0; i<n_info.count; i++)
        {
            if(n_info.info[i].slot == slot)
            {
                if((hop > n_info.info[i].hop) || ((hop == n_info.info[i].hop) && (TOS_NODE_ID > n_info.info[i].id)))
                {
                    slot = slot - 1;
                    NeighbourList_add(&n_info, TOS_NODE_ID, hop, slot);
                    NeighbourList_add(&onehop, TOS_NODE_ID, hop, slot);
                    simdbg("stdout", "Adjusted slot %u.\n", slot);
                }
            }
        }
    }

    /*void send_beacon()*/
    /*{*/
        /*BeaconMessage msg;*/
        /*msg.source_id = TOS_NODE_ID;*/
        /*send_Beacon_message(&msg, AM_BROADCAST_ADDR);*/
    /*}*/

    void send_dissem()
    {
        DissemMessage msg;
        msg.source_id = TOS_NODE_ID;
        msg.N = onehop;
        send_Dissem_message(&msg, AM_BROADCAST_ADDR);
    }

	task void send_message_normal()
	{
		NormalMessage* message;

		simdbgverbose("SourceBroadcasterC", "%s: BroadcastTimer fired.\n", sim_time_string());

		message = call MessageQueue.dequeue();

		if (message != NULL)
		{
			if (send_Normal_message(message, AM_BROADCAST_ADDR))
			{
				call MessagePool.put(message);
			}
			else
			{
				simdbgerror("stdout", "send failed, not returning memory to pool so it will be tried again\n");
			}
		}
		else
		{
			/*DummyNormalMessage dummy_message;*/

			/*send_DummyNormal_message(&dummy_message, AM_BROADCAST_ADDR);*/
		}

        if(slot_active && !(call MessageQueue.empty()))
        {
            post send_message_normal();
        }
	}

    //Main Logic}}}

    //Timers.fired(){{{
    event void InitTimer.fired()
    {
        /*PRINTF0("%s: InitTimer fired.\n", sim_time_string());*/
        call ObjectDetector.start();
        /*call DissemTimer.startOneShot(get_dissem_period());*/
        call BeaconTimer.startOneShot(get_beacon_period());
    }

    event void BeaconTimer.fired()
    {
        if(slot != BOT) send_dissem(); //TODO: Test this doesn't cause problems
        process_dissem();
        call PreSlotTimer.startOneShot(get_beacon_period());
    }

    event void DissemTimer.fired()
    {
        /*
         *PRINTF0("%s: DissemTimer fired.\n", sim_time_string());
         *if(slot != BOT) send_dissem(); //TODO: Test this doesn't cause problems
         *process_dissem();
         *call DissemTimer.startOneShot(get_dissem_period());
         */
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
            post send_message_normal();
        }
        call PostSlotTimer.startOneShot(get_slot_period());
    }

    event void PostSlotTimer.fired()
    {
        uint16_t s = (slot == BOT) ? get_tdma_num_slots() : slot;
        /*PRINTF0("%s: PostSlotTimer fired.\n", sim_time_string());*/
        slot_active = FALSE;
        call BeaconTimer.startOneShot((get_tdma_num_slots()-(s-1))*get_slot_period());
    }

    event void EnqueueNormalTimer.fired()
    {
        if(slot != BOT)
        {
            NormalMessage* message;

            /*simdbg("stdout", "%s: EnqueueNormalTimer fired.\n", sim_time_string());*/
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
            }
        }
        call EnqueueNormalTimer.startOneShot(get_source_period());
    }
    //}}} Timers.fired()

    //Receivers{{{
	void Normal_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
        simdbg("stdout", "Received normal.\n");
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
		case SinkNode: Sink_receive_Normal(rcvd, source_addr); break;
		case NormalNode: Normal_receive_Normal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)


	void x_receive_DummyNormal(const DummyNormalMessage* const rcvd, am_addr_t source_addr)
	{
		METRIC_RCV_DUMMYNORMAL(rcvd);
	}

	RECEIVE_MESSAGE_BEGIN(DummyNormal, Receive)
		case SourceNode:
		case SinkNode:
		case NormalNode: x_receive_DummyNormal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(DummyNormal)

    /*void x_receive_Beacon(const BeaconMessage* const rcvd, am_addr_t source_addr)*/
    /*{*/
        /*[>simdbg("stdout", "Received beacon.\n");<]*/
        /*METRIC_RCV_BEACON(rcvd);*/
        /*IDList_add(&neighbours, source_addr);*/
        /*[>IDList_add(&live, source_addr);<]*/
    /*}*/

    /*RECEIVE_MESSAGE_BEGIN(Beacon, Receive)*/
        /*case SourceNode:*/
        /*case SinkNode:*/
        /*case NormalNode: x_receive_Beacon(rcvd, source_addr); break;*/
    /*RECEIVE_MESSAGE_END(Beacon)*/

    void x_receive_Dissem(const DissemMessage* const rcvd, am_addr_t source_addr)
    {
        int i;
        IDList_add(&neighbours, source_addr);
        NeighbourList_add_info(&onehop, *NeighbourList_get(&(rcvd->N), source_addr));
        if(slot == BOT && NeighbourList_get(&(rcvd->N), source_addr)->slot != BOT)
        {
            OtherInfo* info = OtherList_get(&others, source_addr);
            IDList_add(&potential_parents, source_addr);
            if(info == NULL)
            {
                OtherList_add(&others, OtherInfo_new(source_addr));
                info = OtherList_get(&others, source_addr);
            }
            for(i=0; i<rcvd->N.count; i++)
            {
                if(rcvd->N.info[i].slot == BOT)
                {
                    IDList_add(&(info->N), rcvd->N.info[i].id);
                }
            }
        }

        for(i = 0; i<rcvd->N.count; i++)
        {
            NeighbourList_add_info(&n_info, rcvd->N.info[i]);
        }
    }

    void Sink_receive_Dissem(const DissemMessage* const rcvd, am_addr_t source_addr)
    {
        int i;
        IDList_add(&neighbours, source_addr);
        NeighbourList_add_info(&onehop, *NeighbourList_get(&(rcvd->N), source_addr));
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
