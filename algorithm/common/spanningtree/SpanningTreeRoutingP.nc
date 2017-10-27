
#include "Common.h"

module SpanningTreeRoutingP
{
    provides {
        interface Send[uint8_t client];
        interface Receive[uint8_t id];
        interface Receive as Snoop[uint8_t id];
        interface Intercept[uint8_t id];

        interface Packet;

        interface Compare<spanning_tree_data_header_t> as SpanningTreeHeaderCompare;
    }

    uses {
        interface SpanningTreeInfo as Info;
        interface RootControl;

        interface Random;

        interface AMSend as SubSend;
        interface Receive as SubReceive;
        interface Receive as SubSnoop;

        interface AMPacket as SubAMPacket;
        interface Packet as SubPacket;

        interface PacketAcknowledgements;
        interface LinkEstimator;

        interface Timer<TMilli> as RetransmitTimer;

        interface MetricLogging;

        interface Queue<send_queue_item_t*> as SendQueue;
        interface Pool<send_queue_item_t> as QueuePool;
        interface Pool<message_t> as MessagePool;

        interface Cache<spanning_tree_data_header_t> as SentCache;
    }
}
implementation
{
    uint8_t seqno = 0;

    inline spanning_tree_data_header_t* get_packet_header(message_t* msg)
    {
        return (spanning_tree_data_header_t*)call SubPacket.getPayload(msg, sizeof(spanning_tree_data_header_t));
    }

    // Send / receive implementation

    void signal_send_done(error_t error)
    {
        send_queue_item_t* item = call SendQueue.dequeue();
        spanning_tree_data_header_t* header = get_packet_header(item->msg);

        if (error == SUCCESS)
        {
            call SentCache.insert(*header);
        }

        if (call MessagePool.from(item->msg))
        {
            call MessagePool.put(item->msg);
        }
        else
        {
            signal Send.sendDone[header->sub_id](item->msg, error);
        }

        call QueuePool.put(item);
    }

    void start_retransmit_timer(send_queue_item_t* item)
    {
        if (item->num_retries < SLP_SPANNING_TREE_MAX_RETRIES)
        {
            call RetransmitTimer.startOneShot(50 + (call Random.rand16() % 25));
        }
        else
        {
            signal_send_done(ENOACK);
        }
    }

    bool match_message(const message_t* msg1, const message_t* msg2)
    {
        const spanning_tree_data_header_t* header1 = get_packet_header((message_t*)msg1);
        const spanning_tree_data_header_t* header2 = get_packet_header((message_t*)msg2);

        return memcmp(header1, header2, sizeof(*header1)) == 0;
    }

    task void send_message()
    {
        am_addr_t parent;
        send_queue_item_t* item;

        if (call SendQueue.empty())
        {
            return;
        }

        item = call SendQueue.element(0);

        parent = call Info.get_parent();

        if (parent == AM_BROADCAST_ADDR)
        {
            return;
        }

        if (call PacketAcknowledgements.requestAck(item->msg) == SUCCESS)
        {
            item->ack_requested = TRUE;
        }

        if (call SubSend.send(parent, item->msg, call SubPacket.payloadLength(item->msg)) == SUCCESS)
        {
            item->num_retries += 1;
        }
        else
        {
            start_retransmit_timer(item);
        }
    }

    event void SubSend.sendDone(message_t* msg, error_t error)
    {
        send_queue_item_t* item = call SendQueue.element(0);

        if (error != SUCCESS)
        {
            start_retransmit_timer(item);
        }
        else if (item->ack_requested && !call PacketAcknowledgements.wasAcked(msg))
        {
            call LinkEstimator.txNoAck(call SubAMPacket.destination(msg));

            start_retransmit_timer(item);
        }
        else
        {
            call LinkEstimator.txAck(call SubAMPacket.destination(msg));

            signal_send_done(error);
        }
    }

    event message_t* SubReceive.receive(message_t* msg, void* payload, uint8_t len)
    {
        spanning_tree_data_header_t* header = get_packet_header(msg);
        uint8_t sub_len = call Packet.payloadLength(msg);
        void* sub_payload = call Packet.getPayload(msg, sub_len);

        // Check to see if we have recently passed this message onwards
        if (call SentCache.lookup(*header))
        {
            return msg;
        }

        // Check to see if this message is already queued to be sent
        {
            uint8_t i, s = call SendQueue.size();
            for (i = 0; i != s; ++i)
            {
                const send_queue_item_t* item = call SendQueue.element(i);
                if (match_message(item->msg, msg))
                {
                    return msg;
                }
            }
        }

        if (call RootControl.isRoot())
        {
            signal Receive.receive[header->sub_id](msg, sub_payload, sub_len);
        }
        else
        {
            if (signal Intercept.forward[header->sub_id](msg, sub_payload, sub_len))
            {
                // Forward the message onwards
                send_queue_item_t* item = call QueuePool.get();
                message_t* new_message = call MessagePool.get();

                if (item == NULL || new_message == NULL)
                {
                    if (item != NULL)
                        call QueuePool.put(item);

                    if (msg != NULL)
                        call MessagePool.put(msg);

                    // TODO: report error!
                    return msg;
                }

                memcpy(new_message, msg, sizeof(*new_message));

                item->msg = new_message;
                item->ack_requested = FALSE;
                item->num_retries = 0;

                if (call SendQueue.enqueue(item) == SUCCESS)
                {
                    post send_message();
                }
                else
                {
                    call QueuePool.put(item);
                    call MessagePool.put(new_message);

                    // TODO: report error!
                    return msg;
                }
            }
        }

        return msg;
    }

    event message_t* SubSnoop.receive(message_t* msg, void* payload, uint8_t len)
    {
        spanning_tree_data_header_t* header = get_packet_header(msg);
        uint8_t sub_len = call Packet.payloadLength(msg);
        void* sub_payload = call Packet.getPayload(msg, sub_len);

        signal Snoop.receive[header->sub_id](msg, sub_payload, sub_len);

        return msg;
    }

    event void RetransmitTimer.fired()
    {
        post send_message();
    }

    // Packet implementation
    command void Packet.clear(message_t* msg)
    {
        call SubPacket.clear(msg);
    }

    command uint8_t Packet.payloadLength(message_t* msg)
    {
        return call SubPacket.payloadLength(msg) - sizeof(spanning_tree_data_header_t);
    }

    command void Packet.setPayloadLength(message_t* msg, uint8_t len)
    {
        call SubPacket.setPayloadLength(msg, len + sizeof(spanning_tree_data_header_t));
    }
  
    command uint8_t Packet.maxPayloadLength()
    {
        return call SubPacket.maxPayloadLength() - sizeof(spanning_tree_data_header_t);
    }

    command void* Packet.getPayload(message_t* msg, uint8_t len)
    {
        uint8_t* payload = (uint8_t*)call SubPacket.getPayload(msg, len + sizeof(spanning_tree_data_header_t));
        if (payload != NULL) {
            payload += sizeof(spanning_tree_data_header_t);
        }
        return payload;
    }

    // Send / Receive interface

    command error_t Send.send[uint8_t id](message_t* msg, uint8_t len)
    {
        spanning_tree_data_header_t* header;
        send_queue_item_t* item;

        if (len > call Send.maxPayloadLength[id]())
            return ESIZE;

        // If we haven't got a parent, don't allow the user
        // to attempt to send.
        // TODO: in the future allow this and probably post send_message tasks
        if (call Info.get_parent() == AM_BROADCAST_ADDR)
            return FAIL;

        call Packet.setPayloadLength(msg, len);

        header = get_packet_header(msg);
        header->ultimate_source = TOS_NODE_ID;
        header->seqno = seqno++;
        header->sub_id = id;

        item = call QueuePool.get();
        if (item == NULL)
        {
            // TODO: Report error!
            return ENOMEM;
        }

        item->msg = msg;
        item->ack_requested = FALSE;
        item->num_retries = 0;

        if (call SendQueue.enqueue(item) == SUCCESS)
        {
            post send_message();

            return SUCCESS;
        }
        else
        {
            call QueuePool.put(item);

            // TODO: Report error!
            return ENOMEM;
        }
    }

    command error_t Send.cancel[uint8_t id](message_t* msg)
    {
        // cancel not implemented. will require being able
        // to pull entries out of the queue.
        return FAIL;
    }

    command uint8_t Send.maxPayloadLength[uint8_t id]()
    {
        return call Packet.maxPayloadLength();
    }

    command void* Send.getPayload[uint8_t client](message_t* msg, uint8_t len)
    {
        return call Packet.getPayload(msg, len);
    }


    // Default events

    default event void Send.sendDone[uint8_t client](message_t* msg, error_t error)
    {
    }

    default event bool Intercept.forward[uint8_t id](message_t* msg, void* payload, uint8_t len)
    {
        return TRUE;
    }

    default event message_t* Receive.receive[uint8_t id](message_t* msg, void* payload, uint8_t len)
    {
        return msg;
    }

    default event message_t* Snoop.receive[uint8_t id](message_t* msg, void* payload, uint8_t len)
    {
        return msg;
    }

    // LinkEstimator

    event void LinkEstimator.evicted(am_addr_t neighbor)
    {
        
    }

    // Compare

    command bool SpanningTreeHeaderCompare.equals(const spanning_tree_data_header_t* a, const spanning_tree_data_header_t* b)
    {
        return a->ultimate_source == b->ultimate_source &&
               a->seqno == b->seqno &&
               a->sub_id == b->sub_id;
    }
}
