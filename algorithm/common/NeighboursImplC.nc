#include "NeighboursRtxInfo.h"

#include "Common.h"
#include "SendReceiveFunctions.h"

generic module NeighboursImplC(
	typedef Info,
	typedef BeaconMessage,
	typedef PollMessage)
{
	provides interface Neighbours<Info, BeaconMessage, PollMessage>;

	uses interface Dictionary<am_addr_t, Info> as NeighbourDict;
	uses interface Dictionary<am_addr_t, NeighboursRtxInfo> as NeighbourRtxDict;

	uses interface Timer<TMilli> as BeaconSenderTimer;

	uses interface Leds;
	uses interface Random;
	uses interface Crc;

#ifdef METRIC_LOGGING_NEEDS_LOCALTIME
	uses interface LocalTime<TMilli>;
#endif

	uses interface AMPacket;

	uses interface AMSend as BeaconSend;
	uses interface Receive as BeaconReceive;

	uses interface AMSend as PollSend;
	uses interface Receive as PollReceive;

	uses interface MetricLogging;
	uses interface MetricHelpers;
	uses interface NodeType;
}
implementation
{
#define BEACON_FAST_SEND_DELAY_FIXED 35
#define BEACON_FAST_SEND_DELAY_RANDOM 50

#define BEACON_SHORT_SEND_DELAY_FIXED 15
#define BEACON_SHORT_SEND_DELAY_RANDOM 10

#define BEACON_RETRY_SEND_DELAY 65

#define MIN_MESSAGES_BEFORE_EVICT 12
#define EVICT_DELIVERY_THRESHOLD_PC 10

	// Neighbour management

	command uint16_t Neighbours.max_size()
	{
		return call NeighbourDict.max_size();
	}

	command uint16_t Neighbours.count()
	{
		return call NeighbourDict.count();
	}

	command Info* Neighbours.begin()
	{
		return call NeighbourDict.begin();
	}

	command Info* Neighbours.end()
	{
		return call NeighbourDict.end();
	}

	command const am_addr_t* Neighbours.beginKeys()
	{
		return call NeighbourDict.beginKeys();
	}

	command const am_addr_t* Neighbours.endKeys()
	{
		return call NeighbourDict.endKeys();
	}

	command Info* Neighbours.get_from_iter(const am_addr_t* iter)
	{
		return call NeighbourDict.get_from_iter(iter);
	}

	command error_t Neighbours.record(am_addr_t address, const Info* info)
	{
		error_t result = SUCCESS;
		Info* stored_info = call NeighbourDict.get(address);

		if (stored_info)
		{
			signal Neighbours.perform_update(stored_info, info);
		}
		else
		{
			bool put_result = call NeighbourDict.put(address, *info);

			if (!put_result)
			{
				result = ENOMEM;
			}
		}

		return result;
	}

	command error_t Neighbours.pin(am_addr_t address)
	{
		NeighboursRtxInfo* stored_info = call NeighbourRtxDict.get(address);

		if (!stored_info)
		{
			static const NeighboursRtxInfo def = {0, 0, 0};

			bool put_result = call NeighbourRtxDict.put(address, def);

			if (!put_result)
			{
				return ENOMEM;
			}

			stored_info = call NeighbourRtxDict.get(address);
		}

		stored_info->flags |= NEIGHBOUR_INFO_PIN;

		return SUCCESS;
	}

	command error_t Neighbours.unpin(am_addr_t address)
	{
		NeighboursRtxInfo* stored_info = call NeighbourRtxDict.get(address);

		if (!stored_info)
		{
			return EALREADY;
		}

		stored_info->flags &= ~NEIGHBOUR_INFO_PIN;

		return SUCCESS;
	}

	void consider_neighbour_eviction(am_addr_t address, const NeighboursRtxInfo* info)
	{
		const uint16_t total_tx = info->rtx_success + info->rtx_failure;

		// Wait for at least MIN_MESSAGES_BEFORE_EVICT transmission before considering evictions
		if (total_tx < MIN_MESSAGES_BEFORE_EVICT)
		{
			return;
		}

		// If EVICT_DELIVERY_THRESHOLD_PC% or less delivery ratio, then evict
		if (info->rtx_success <= total_tx / EVICT_DELIVERY_THRESHOLD_PC)
		{
			// Neighbour is pinned, so cannot evict
			if ((info->flags & NEIGHBOUR_INFO_PIN) != 0)
			{
				ERROR_OCCURRED(ERROR_UNKNOWN, "Wanted to evict pinned neighbour %u\n", address);
			}
			else
			{
				simdbg("stdout", "Evicting %u due to %u out of %u\n",
					address, info->rtx_success, total_tx);

				call NeighbourDict.remove(address);
				call NeighbourRtxDict.remove(address);
			}
		}
	}

	command error_t Neighbours.rtx_result(am_addr_t address, bool succeeded)
	{
		NeighboursRtxInfo* stored_info = call NeighbourRtxDict.get(address);

		if (!stored_info)
		{
			static const NeighboursRtxInfo def = {0, 0, 0};

			bool put_result = call NeighbourRtxDict.put(address, def);

			if (!put_result)
			{
				return ENOMEM;
			}

			stored_info = call NeighbourRtxDict.get(address);
		}

		if (succeeded)
		{
			stored_info->rtx_success += 1;
		}
		else
		{
			stored_info->rtx_failure += 1;
		}

		consider_neighbour_eviction(address, stored_info);

		return SUCCESS;
	}

	// Message management

	bool busy = FALSE;
	message_t packet;

	USE_MESSAGE_NO_EXTRA_TO_SEND(Beacon);
	USE_MESSAGE_NO_EXTRA_TO_SEND(Poll);

	command void Neighbours.poll(const PollMessage* data)
	{
		// Requests that a poll message is sent
		send_Poll_message(data, AM_BROADCAST_ADDR);
	}

	command void Neighbours.fast_beacon()
	{
		// Requests that a beacon message is sent

		// Send faster to try to get back to polling node before it gives up sending the message
		call BeaconSenderTimer.startOneShot(BEACON_FAST_SEND_DELAY_FIXED + (call Random.rand16() % BEACON_FAST_SEND_DELAY_RANDOM));
	}

	command void Neighbours.slow_beacon()
	{
		// Requests that a beacon message is sent

		// Send faster to try to get back to polling node before it gives up sending the message
		call BeaconSenderTimer.startOneShot(BEACON_SHORT_SEND_DELAY_FIXED + (call Random.rand16() % BEACON_SHORT_SEND_DELAY_RANDOM));
	}

	event void BeaconSenderTimer.fired()
	{
		BeaconMessage message;

		signal Neighbours.generate_beacon(&message);

		if (!send_Beacon_message(&message, AM_BROADCAST_ADDR))
		{
			call BeaconSenderTimer.startOneShot(BEACON_RETRY_SEND_DELAY);
		}
	}

	void x_receive_Beacon(const BeaconMessage* const rcvd, am_addr_t source_addr)
	{
		signal Neighbours.rcv_beacon(rcvd, source_addr);
	}

	RECEIVE_MESSAGE_BEGIN(Beacon, Receive)
		default: x_receive_Beacon(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END_NO_DEFAULT(Beacon)

	void x_receive_Poll(const PollMessage* const rcvd, am_addr_t source_addr)
	{
		signal Neighbours.rcv_poll(rcvd, source_addr);

		call Neighbours.fast_beacon();
	}

	RECEIVE_MESSAGE_BEGIN(Poll, Receive)
		default: x_receive_Poll(rcvd, source_addr); break;
	RECEIVE_MESSAGE_END_NO_DEFAULT(Poll)
}
