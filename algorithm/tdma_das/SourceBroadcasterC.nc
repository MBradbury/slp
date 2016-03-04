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

#undef BOTTOM
#define BOTTOM UINT16_MAX

#define BEACON_PERIOD_MS 2000
#define WAVE_PERIOD_MS 20000
#define SLOT_PERIOD_MS 500

#define TDMA_NUM_SLOTS 50

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;

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
    void send_beacon();
    void dissem();

    bool start = TRUE;
    bool c = FALSE;
    IDList neighbours;
    IDList live;
    SlotList slots;
    uint16_t slot = BOTTOM;
    uint16_t hop = BOTTOM;
    uint16_t parent = BOTTOM;
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

    uint32_t get_tdma_num_slots()
    {
        return TDMA_NUM_SLOTS;
    }


	uint32_t extra_to_send = 0;

	bool busy = FALSE;
	message_t packet;

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
			//call BroadcastTimer.startOneShot(get_broadcast_period());
            send_beacon();
            dissem();
            call WaveTimer.startOneShot(get_wave_period());
            call BeaconTimer.startOneShot(get_beacon_period());
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
    }

    void dissem()
    {
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
        else if((type != SinkNode) && (slot != BOTTOM))
        {
            WaveMessage msg;
            msg.source_id = TOS_NODE_ID;
            msg.neighbours = IDList_minus_parent(&neighbours, parent);
            msg.slot = slot;
            msg.hop = hop;
            send_Wave_message(&msg, AM_BROADCAST_ADDR);
        }
    }


    void process_waves()
    {
        if(c)
        {
            if(slot != BOTTOM)
            {
                SlotList_add(&slots, TOS_NODE_ID, slot, hop, neighbours);
            }

            if(SlotList_collision(&slots))
            {
                uint16_t i,j;
                for (i = 0; i < slots.count; i++) {
                    for (j = i + 1; j < slots.count; j++) {
                        if (slots.slots[i].slot == slots.slots[j].slot) {
                            CollisionMessage msg;
                            msg.source_id = TOS_NODE_ID;
                            msg.slots = SlotList_n_from_s(&slots, slots.slots[i].slot);
                            send_Collision_message(&msg, AM_BROADCAST_ADDR);
                        }
                    }
                }
            }
            else
            {
                if(type != SinkNode && (slot == BOTTOM || parent == BOTTOM || hop == BOTTOM))
                {
                    SlotList possible_parents;
                    SlotDetails details = SlotList_min_h(&slots);
                    hop = details.hop + 1;
                    slot = details.slot - rank(&(details.neighbours), TOS_NODE_ID);
                    possible_parents = SlotList_n_from_sh(&slots, details.slot, details.hop);
                    parent = possible_parents.slots[rand() % possible_parents.count].id;
                }
            }
            c = FALSE;
        }
        IDList_clear(&live);
    }

    event void BeaconTimer.fired()
    {
        /*call ObjectDetector.start();*/
        /*call BroadcastTimer.startOneShot(get_broadcast_period());*/
        send_beacon();
        call PreSlotTimer.startOneShot(get_beacon_period());
    }

    event void WaveTimer.fired()
    {
        //dissem();
        process_waves();
        call WaveTimer.startOneShot(get_wave_period());
    }

    event void PreSlotTimer.fired()
    {
        call SlotTimer.startOneShot(slot*get_slot_period());
    }

    void send_message_source();
    /*void send_message_normal();*/
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

    event void SlotTimer.fired()
    {
        if(type == SourceNode)
        {
            send_message_source();
        }
        slot_active = TRUE;
        /*send_message_normal();*/
        post send_message_normal();
        call PostSlotTimer.startOneShot(get_slot_period());
    }

    event void PostSlotTimer.fired()
    {
        slot_active = FALSE;
        call BeaconTimer.startOneShot((get_tdma_num_slots()-(slot-1))*get_slot_period());
    }

    event void EnqueueNormalTimer.fired()
    {
    }


    void send_message_source()
    {
        NormalMessage* message;

        simdbgverbose("SourceBroadcasterC", "%s: EnqueueNormalTimer fired.\n", sim_time_string());

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

        call EnqueueNormalTimer.startOneShot(get_source_period());
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


	void Normal_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
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
        c = TRUE;
        IDList_add(&live, source_addr);
        SlotList_add(&slots, source_addr, rcvd->slot, rcvd->hop, rcvd->neighbours);
        return;
    }

    RECEIVE_MESSAGE_BEGIN(Wave, Receive)
        case SourceNode:
        case NormalNode: x_receive_Wave(rcvd, source_addr); break;
    RECEIVE_MESSAGE_END(Wave)

    void x_receive_Collision(const CollisionMessage* const rcvd, am_addr_t source_addr)
    {
        if(SlotList_contains_id(&(rcvd->slots), TOS_NODE_ID) && slot != BOTTOM)
        {
            IDList ids = SlotList_to_ids(&(rcvd->slots));
            slot = slot - rank(&ids, TOS_NODE_ID) + 1;
        }
    }

    RECEIVE_MESSAGE_BEGIN(Collision, Receive)
        case SourceNode:
        case NormalNode: x_receive_Collision(rcvd, source_addr); break;
    RECEIVE_MESSAGE_END(Collision)
}
