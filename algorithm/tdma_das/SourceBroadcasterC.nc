#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "NormalMessage.h"
#include "DummyNormalMessage.h"
#include "BeaconMessage.h"
#include "WaveMessage.h"
#include "CollisionMessage.h"

#include "utils.h"

#include <Timer.h>
#include <TinyError.h>

#include <assert.h>
#include <stdlib.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_DUMMYNORMAL(msg) METRIC_RCV(DummyNormal, source_addr, source_addr, BOTTOM, 1)
#define METRIC_RCV_BEACON(msg) METRIC_RCV(Beacon, source_addr, msg->source_id, BOTTOM, 1)

#define BOT UINT16_MAX

#define BEACON_PERIOD_MS 500
#define WAVE_PERIOD_MS 1000
#define SLOT_PERIOD_MS 100
#define INIT_PERIOD_MS 2000

#define TDMA_NUM_SLOTS 50

#define PRINTF(node, ...) if(TOS_NODE_ID==node)simdbg("stdout", __VA_ARGS__);
#define PRINTF0(...) PRINTF(0,__VA_ARGS__)

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;

    uses interface Timer<TMilli> as InitTimer;
	uses interface Timer<TMilli> as EnqueueNormalTimer;
	//uses interface Timer<TMilli> as BroadcastTimer;
    uses interface Timer<TMilli> as BeaconTimer;
    uses interface Timer<TMilli> as WaveTimer;
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

    uses interface AMSend as BeaconSend;
    uses interface Receive as BeaconReceive;

    uses interface AMSend as WaveSend;
    uses interface Receive as WaveReceive;

    uses interface AMSend as CollisionSend;
    uses interface Receive as CollisionReceive;

	uses interface ObjectDetector;
	uses interface SourcePeriodModel;

	uses interface SequenceNumbers as NormalSeqNos;
}

implementation
{
    //Initialisation variables{{{
    void send_beacon();
    void dissem();

    bool initialise = TRUE;

    bool start = TRUE;
    bool c = FALSE;
    IDList neighbours;
    IDList live;
    SlotList slots;
    uint16_t slot = BOT;
    uint16_t hop = BOT;
    uint16_t parent = BOT;
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

    uint32_t get_wave_period()
    {
        return WAVE_PERIOD_MS;
    }

    uint32_t get_slot_period()
    {
        return SLOT_PERIOD_MS;
    }

    uint32_t get_init_period()
    {
        return INIT_PERIOD_MS;
    }

    uint32_t get_tdma_num_slots()
    {
        return TDMA_NUM_SLOTS;
    }
    //###################}}}


	event void Boot.booted()
	{
        live = IDList_new();
        neighbours = IDList_new();
        slots = SlotList_new();

		simdbgverbose("Boot", "%s: Application booted.\n", sim_time_string());

		if (TOS_NODE_ID == SINK_NODE_ID)
		{
			type = SinkNode;
			simdbg("Node-Change-Notification", "The node has become a Sink\n");
		}

		call RadioControl.start();
	}

    void normal_message_hack();
    void wave_message_hack();

	event void RadioControl.startDone(error_t err)
	{
		if (err == SUCCESS)
		{
			simdbgverbose("SourceBroadcasterC", "%s: RadioControl started.\n", sim_time_string());

            /*normal_message_hack();*/
            /*wave_message_hack();*/
            send_beacon(); //Need this before dissem() or segmentation fault
            /*dissem(); //Need this here or floating point exception*/
            /*call ObjectDetector.start();*/
            /*call WaveTimer.startOneShot(get_wave_period());*/
            /*call BeaconTimer.startOneShot(get_init_period());*/
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

		}
	}

	event void ObjectDetector.stoppedDetecting()
	{
		if (type == SourceNode)
		{

			type = NormalNode;

			simdbg_clear("Metric-SOURCE_CHANGE", "unset,%u\n", TOS_NODE_ID);
			simdbg("Node-Change-Notification", "The node has become a Normal\n");
		}
	}

	USE_MESSAGE(Normal);
	USE_MESSAGE(DummyNormal);
    USE_MESSAGE(Beacon);
    USE_MESSAGE(Wave);
    USE_MESSAGE(Collision);

    void send_beacon()
    {
        BeaconMessage msg;
        msg.source_id = TOS_NODE_ID;
        send_Beacon_message(&msg, AM_BROADCAST_ADDR);
        /*PRINTF0("Beacon sent.\n");*/
    }

    void dissem()
    {
        /*PRINTF0("Dissem started...\n");*/
        SlotList_clear(&slots);

        if(type == SinkNode && start)
        {
            WaveMessage msg;
            msg.source_id = TOS_NODE_ID;
            msg.neighbours = neighbours;
            msg.slot = get_tdma_num_slots();
            msg.hop = hop;
            send_Wave_message(&msg, AM_BROADCAST_ADDR);

            start = FALSE;
        }
        else if((type != SinkNode) && (slot != BOT))
        {
            WaveMessage msg;
            msg.source_id = TOS_NODE_ID;
            msg.neighbours = IDList_minus_parent(&neighbours, parent);
            msg.slot = slot;
            msg.hop = hop;
            send_Wave_message(&msg, AM_BROADCAST_ADDR);
            /*simdbg("stdout", "Sent wave from normal.\n");*/
        }
    }


    void wave_message_hack()
    {
        WaveMessage msg;
        msg.source_id = TOS_NODE_ID;
        //msg.neighbours = IDList_minus_parent(&neighbours, parent);
        msg.slot = 0;
        msg.hop = 0;
        send_Wave_message(&msg, AM_BROADCAST_ADDR);
    }

    void process_waves()
    {
        /*simdbg("stdout", "%s: Processing waves...\n", sim_time_string());*/
        if(c)
        {
            if(slot != BOT)
            {
                /*simdbg("stdout", "Adding self to slot list.\n");*/
                SlotList_add(&slots, TOS_NODE_ID, slot, hop, neighbours);
            }

            if(SlotList_collision(&slots))
            {
                uint16_t i,j;
                /*simdbg("stdout", "Processed collision.\n");*/
                for (i = 0; i < slots.count; i++) {
                    for (j = i + 1; j < slots.count; j++) {
                        if (slots.slots[i].slot == slots.slots[j].slot) {
                            CollisionMessage msg;
                            msg.source_id = TOS_NODE_ID;
                            msg.slots = SlotList_n_from_s(&slots, slots.slots[i].slot);
                            send_Collision_message(&msg, AM_BROADCAST_ADDR);
                            simdbg("stdout", "Sending collision message...\n");
                        }
                    }
                }
            }
            else
            {
                if(type != SinkNode && (slot == BOT || parent == BOT || hop == BOT))
                {
                    SlotList possible_parents;
                    SlotDetails details = SlotList_min_h(&slots);
                    /*simdbg("stdout", "Selecting slot...\n");*/
                    hop = details.hop + 1;
                    /*simdbg("stdout", "Choosing slot...\n");*/
                    slot = details.slot - rank(&(details.neighbours), TOS_NODE_ID);
                    /*simdbg("stdout", "Selecting possible parents...\n");*/
                    possible_parents = SlotList_n_from_sh(&slots, details.slot, details.hop);
                    /*simdbg("stdout", "Selecting parent...\n");*/
                    if(possible_parents.count == 0)
                    {
                        /*simdbg("stdout", "No parents to choose from.\n");*/
                        parent = BOT;
                    }
                    else
                    {
                        int r = rand();
                        int i = r % possible_parents.count;
                        /*simdbg("stdout", "Selecting parent 2...\n");*/
                        /*simdbg("stdout", "%u possible parents, selected %i\n", possible_parents.count, i);*/
                        parent = possible_parents.slots[i].id;
                    }
                    simdbg("stdout", "Chosen slot %u.\n", slot);
                }
            }
            c = FALSE;
        }
        IDList_clear(&live);
        /*simdbg("stdout", "Waves processed.\n");*/
    }

    void send_message_source();
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
			DummyNormalMessage dummy_message;

			send_DummyNormal_message(&dummy_message, AM_BROADCAST_ADDR);
		}

        if(slot_active && !(call MessageQueue.empty()))
        {
            post send_message_normal();
        }
	}

    //Timers.fired(){{{
    event void InitTimer.fired()
    {
        PRINTF0("%s: InitTimer fired.\n", sim_time_string());
        call ObjectDetector.start();
        dissem();
        call WaveTimer.startOneShot(get_wave_period());
        call BeaconTimer.startOneShot(get_beacon_period());
    }

    event void BeaconTimer.fired()
    {
        PRINTF0("%s: BeaconTimer fired.\n", sim_time_string());
        if(initialise)
        {
            send_beacon();
            /*dissem();*/
            initialise = FALSE;
        }
        /*dissem();*/
        call PreSlotTimer.startOneShot(get_beacon_period());
    }

    event void WaveTimer.fired()
    {
        PRINTF0("%s: WaveTimer fired.\n", sim_time_string());
        dissem();
        process_waves();
        call WaveTimer.startOneShot(get_wave_period());
    }

    event void PreSlotTimer.fired()
    {
        uint16_t s = (slot == BOT) ? get_tdma_num_slots() : slot;
        PRINTF0("%s: PreSlotTimer fired.\n", sim_time_string());
        call SlotTimer.startOneShot(s*get_slot_period());
    }


    event void SlotTimer.fired()
    {
        PRINTF0("%s: SlotTimer fired.\n", sim_time_string());
        slot_active = TRUE;
        if(slot != BOT)
        {
            if(type == SourceNode)
            {
                send_message_source();
            }
            post send_message_normal();
        }
        call PostSlotTimer.startOneShot(get_slot_period());
    }

    event void PostSlotTimer.fired()
    {
        uint16_t s = (slot == BOT) ? get_tdma_num_slots() : slot;
        PRINTF0("%s: PostSlotTimer fired.\n", sim_time_string());
        slot_active = FALSE;
        call BeaconTimer.startOneShot((get_tdma_num_slots()-(s-1))*get_slot_period());
    }

    event void EnqueueNormalTimer.fired()
    {
    }
    //}}} Timers.fired()


    void send_message_source()
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
        }

    }

    void normal_message_hack()
    {
        NormalMessage msg;
        msg.sequence_number = 0;
        msg.source_distance = 0;
        msg.source_id = TOS_NODE_ID;
        send_Normal_message(&msg, AM_BROADCAST_ADDR);
    }

/*
 *    void send_message_normal()
 *    {
 *        NormalMessage* message;
 *
 *        simdbgverbose("SourceBroadcasterC", "%s: BroadcastTimer fired.\n", sim_time_string());
 *
 *        message = call MessageQueue.dequeue();
 *
 *        if (message != NULL)
 *        {
 *            if (send_Normal_message(message, AM_BROADCAST_ADDR))
 *            {
 *                call MessagePool.put(message);
 *            }
 *            else
 *            {
 *                simdbgerror("stdout", "send failed, not returning memory to pool so it will be tried again\n");
 *            }
 *        }
 *        else
 *        {
 *            DummyNormalMessage dummy_message;
 *
 *            send_DummyNormal_message(&dummy_message, AM_BROADCAST_ADDR);
 *        }
 *
 *        //call BroadcastTimer.startOneShot(get_broadcast_period());
 *    }
 */

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
        simdbg("stdout", "Received normal.\n");
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

    void x_receive_Beacon(const BeaconMessage* const rcvd, am_addr_t source_addr)
    {
        /*simdbg("stdout", "Received beacon.\n");*/
        METRIC_RCV_BEACON(rcvd);
        IDList_add(&neighbours, source_addr);
        IDList_add(&live, source_addr);
    }

    RECEIVE_MESSAGE_BEGIN(Beacon, Receive)
        case SourceNode:
        case SinkNode:
        case NormalNode: x_receive_Beacon(rcvd, source_addr); break;
    RECEIVE_MESSAGE_END(Beacon)

    void x_receive_Wave(const WaveMessage* const rcvd, am_addr_t source_addr)
    {
        /*simdbg("stdout", "Received wave from %u.\n", source_addr);*/
        c = TRUE;
        IDList_add(&live, source_addr);
        SlotList_add(&slots, source_addr, rcvd->slot, rcvd->hop, rcvd->neighbours);
    }

    RECEIVE_MESSAGE_BEGIN(Wave, Receive)
        case SourceNode:
        case NormalNode: x_receive_Wave(rcvd, source_addr); break;
    RECEIVE_MESSAGE_END(Wave)

    void x_receive_Collision(const CollisionMessage* const rcvd, am_addr_t source_addr)
    {
        simdbg("stdout", "Received collision.\n");
        if(SlotList_contains_id(&(rcvd->slots), TOS_NODE_ID) && slot != BOT)
        {
            IDList ids = SlotList_to_ids(&(rcvd->slots));
            slot = slot - rank(&ids, TOS_NODE_ID) + 1;
        }
    }

    RECEIVE_MESSAGE_BEGIN(Collision, Receive)
        case SourceNode:
        case NormalNode: x_receive_Collision(rcvd, source_addr); break;
    RECEIVE_MESSAGE_END(Collision)
    //}}}Receivers
}
