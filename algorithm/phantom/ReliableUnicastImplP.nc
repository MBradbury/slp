#include "Constants.h"

// Modified to add metadata:
#include "TossimRadioMsg.h"

// Mostly taken from PacketLink

module ReliableUnicastImplP
{
	provides
	{
		interface AMSend;
		interface PacketLink;
	}

	uses
	{
		interface AMSend as Sender;
		interface State as SendState;
		interface PacketAcknowledgements;

		interface Timer<TMilli> as DelayTimer;
	}
}
implementation
{
	
	/** The message currently being sent */
	message_t* currentSendMsg;
	
	/** Length of the current send message */
	uint8_t currentSendLen;
	
	/** The length of the current send message */
	uint16_t totalRetries;

	am_addr_t currentSendAddr;
	
	
	/**
	 * Send States
	 */
	enum {
		S_IDLE = 0,
		S_SENDING,
	};
	
	inline tossim_metadata_t* getMetadata(message_t* msg)
	{
		return (tossim_metadata_t*)(&msg->metadata);
	}
	
	/***************** Prototypes ***************/
	task void send();
	void signalDone(error_t error);
		
	/***************** PacketLink Commands ***************/
	/**
	 * Set the maximum number of times attempt message delivery
	 * Default is 0
	 * @param msg
	 * @param maxRetries the maximum number of attempts to deliver
	 *     the message
	 */
	command void PacketLink.setRetries(message_t *msg, uint16_t maxRetries)
	{
		getMetadata(msg)->maxRetries = maxRetries;
	}

	/**
	 * Set a delay between each retry attempt
	 * @param msg
	 * @param retryDelay the delay between retry attempts, in milliseconds
	 */
	command void PacketLink.setRetryDelay(message_t *msg, uint16_t retryDelay)
	{
		getMetadata(msg)->retryDelay = retryDelay;
	}

	/** 
	 * @return the maximum number of retry attempts for this message
	 */
	command uint16_t PacketLink.getRetries(message_t *msg)
	{
		return getMetadata(msg)->maxRetries;
	}

	/**
	 * @return the delay between retry attempts in ms for this message
	 */
	command uint16_t PacketLink.getRetryDelay(message_t *msg)
	{
		return getMetadata(msg)->retryDelay;
	}

	/**
	 * @return TRUE if the message was delivered.
	 */
	command bool PacketLink.wasDelivered(message_t *msg)
	{
		return call PacketAcknowledgements.wasAcked(msg);
	}
	
	/***************** Send Commands ***************/
	/**
	 * Each call to this send command gives the message a single
	 * DSN that does not change for every copy of the message
	 * sent out.  For messages that are not acknowledged, such as
	 * a broadcast address message, the receiving end does not
	 * signal receive() more than once for that message.
	 */
	command error_t AMSend.send(am_addr_t addr, message_t *msg, uint8_t len)
	{
		error_t error;
		if (call SendState.requestState(S_SENDING) == SUCCESS)
		{
			currentSendAddr = addr;
			currentSendMsg = msg;
			currentSendLen = len;
			totalRetries = 0;

			if (call PacketLink.getRetries(msg) > 0 && addr != AM_BROADCAST_ADDR)
			{
				call PacketAcknowledgements.requestAck(msg);
			}
		 
			if ((error = call Sender.send(addr, msg, len)) != SUCCESS)
			{
				call SendState.toIdle();
			}
			
			return error;
		}

		return EBUSY;
	}

	command error_t AMSend.cancel(message_t *msg)
	{
		if (currentSendMsg == msg)
		{
			call SendState.toIdle();
			return call Sender.cancel(msg);
		}
		
		return FAIL;
	}
	
	
	command uint8_t AMSend.maxPayloadLength()
	{
		return call Sender.maxPayloadLength();
	}

	command void* AMSend.getPayload(message_t* msg, uint8_t len)
	{
		return call Sender.getPayload(msg, len);
	}
	
	
	/***************** Sender Events ***************/
	event void Sender.sendDone(message_t* msg, error_t error)
	{
		if (call SendState.getState() == S_SENDING)
		{
			totalRetries++;

			if (call PacketAcknowledgements.wasAcked(msg))
			{
				signalDone(SUCCESS);
				return;
			}
			else if (totalRetries < call PacketLink.getRetries(currentSendMsg) && currentSendAddr != AM_BROADCAST_ADDR)
			{
				if (call PacketLink.getRetryDelay(currentSendMsg) > 0)
				{
					// Resend after some delay
					call DelayTimer.startOneShot(call PacketLink.getRetryDelay(currentSendMsg));	
				}
				else
				{
					// Resend immediately
					post send();
				}
				
				return;
			}
		}
		
		signalDone(error);
	}
	
	
	/***************** Timer Events ****************/  
	/**
	 * When this timer is running, that means we're sending repeating messages
	 * to a node that is receive check duty cycling.
	 */
	event void DelayTimer.fired()
	{
		if (call SendState.getState() == S_SENDING)
		{
			post send();
		}
	}
	
	/***************** Tasks ***************/
	task void send()
	{
		if (call PacketLink.getRetries(currentSendMsg) > 0 && currentSendAddr != AM_BROADCAST_ADDR)
		{
			call PacketAcknowledgements.requestAck(currentSendMsg);
		}
		
		if (call Sender.send(currentSendAddr, currentSendMsg, currentSendLen) != SUCCESS)
		{
			post send();
		}
	}
	
	/***************** Functions ***************/  
	void signalDone(error_t error)
	{
		call DelayTimer.stop();
		call SendState.toIdle();

		// Update only if retries were explicitly asked for
		if (getMetadata(currentSendMsg)->maxRetries > 0)
		{
			getMetadata(currentSendMsg)->maxRetries = totalRetries;
		}

		signal AMSend.sendDone(currentSendMsg, error);
	}
}
