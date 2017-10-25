#include "Constants.h"
#include "Common.h"
#include "SendReceiveFunctions.h"

#include "NormalMessage.h"
#include "EmptyNormalMessage.h"

#define __computed_include(x) #x
#define _computed_include(x) __computed_include(x)
#define computed_include(x) _computed_include(x)
#include computed_include(GENETIC_HEADER)

#include <Timer.h>
#include <TinyError.h>

#include <stdlib.h>

#define METRIC_RCV_NORMAL(msg) METRIC_RCV(Normal, source_addr, msg->source_id, msg->sequence_number, msg->source_distance + 1)
#define METRIC_RCV_EMPTYNORMAL(msg) METRIC_RCV(EmptyNormal, source_addr, source_addr, BOTTOM, 1)

#define BOT UINT16_MAX

#define PRINTF(node, ...) if(TOS_NODE_ID==node)simdbgverbose("stdout", __VA_ARGS__);
#define PRINTF0(...) PRINTF(0,__VA_ARGS__)

module SourceBroadcasterC
{
	uses interface Boot;
	uses interface Leds;
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

    uses interface FaultModel;

    provides interface SourcePeriodConverter;
}

implementation
{
    //Initialisation variables{{{
    enum
	{
		SourceNode,
        SinkNode,
        NormalNode,
        PathNode,
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
        return GA_TOTAL_SLOTS;
    }


    //Setter Functions{{{
    event void TDMA.slot_changed(uint16_t old_slot, uint16_t new_slot)
    {
        return;
    }

    //Startup Events
	event void Boot.booted()
	{
		METRIC_BOOT();

        call MessageType.register_pair(NORMAL_CHANNEL, "Normal");
        call MessageType.register_pair(EMPTYNORMAL_CHANNEL, "EmptyNormal");

        call NodeType.register_pair(SourceNode, "SourceNode");
        call NodeType.register_pair(SinkNode, "SinkNode");
        call NodeType.register_pair(NormalNode, "NormalNode");
        call NodeType.register_pair(PathNode, "PathNode");

        call FaultModel.register_pair(PathFaultPoint, "PathFaultPoint");

        if (call NodeType.is_node_sink())
        {
            call NodeType.init(SinkNode);
        }
        else if (ga_is_in_path(TOS_NODE_ID))
        {
            call NodeType.init(PathNode);
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

    command uint32_t SourcePeriodConverter.convert(uint32_t period)
    {
        return (uint32_t)ceil((DISSEM_PERIOD_MS + SLOT_PERIOD_MS*GA_TOTAL_SLOTS)/(period/1000.0));
    }

    //Startup Events}}}

    //Main Logic{{{

	USE_MESSAGE_WITH_CALLBACK_NO_EXTRA_TO_SEND(Normal);
    USE_MESSAGE_NO_EXTRA_TO_SEND(EmptyNormal);

    void init(void)
    {
        if (call NodeType.get() == SinkNode)
        {
            call TDMA.set_slot(get_tdma_num_slots());
        }
        else
        {
            call TDMA.set_slot(ga_slot_assignments[TOS_NODE_ID]);
        }

        if(ga_is_in_path(TOS_NODE_ID)) {
            call FaultModel.fault_point(PathFaultPoint);
        }
    }

    event void DissemTimerSender.fired()
    {
        return;
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
    event bool TDMA.dissem_fired()
    {
        const uint32_t now = call LocalTime.get();
        METRIC_START_PERIOD();
        if(call NodeType.get() != SourceNode) MessageQueue_clear(); //XXX Dirty hack to stop other nodes sending stale messages
        call DissemTimerSender.startOneShotAt(now, (uint32_t)(get_slot_period() * random_float()));
        return TRUE;
    }

    event void TDMA.slot_started()
    {
        if(call NodeType.get() != SinkNode)
        {
            post send_normal();
        }
    }

    event void TDMA.slot_finished()
    {
        return;
    }

    event void SourcePeriodModel.fired()
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
    //}}} Timers.fired()

    //Receivers{{{
	void Normal_receive_Normal(const NormalMessage* const rcvd, am_addr_t source_addr)
	{
        /*simdbgverbose("stdout", "Received normal.\n");*/
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
		if (call NormalSeqNos.before(TOS_NODE_ID, rcvd->sequence_number))
		{
            call NormalSeqNos.update(TOS_NODE_ID, rcvd->sequence_number);

			METRIC_RCV_NORMAL(rcvd);
		}
	}

	RECEIVE_MESSAGE_BEGIN(Normal, Receive)
        case SourceNode: break;
		case SinkNode: Sink_receive_Normal(rcvd, source_addr); break;
        case PathNode:
		case NormalNode: Normal_receive_Normal(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END(Normal)

    void x_receive_EmptyNormal(const EmptyNormalMessage* const rcvd, am_addr_t source_addr)
    {
        METRIC_RCV_EMPTYNORMAL(rcvd);
    }

    RECEIVE_MESSAGE_BEGIN(EmptyNormal, Receive)
        case SourceNode:
        case PathNode:
        case NormalNode:
        case SinkNode:   x_receive_EmptyNormal(rcvd, source_addr); break;
    RECEIVE_MESSAGE_END(EmptyNormal)
}
