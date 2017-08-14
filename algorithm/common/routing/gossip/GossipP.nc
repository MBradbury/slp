
#include "Gossip.h"

generic module GossipP(typedef Message, uint32_t wait_period)
{
	provides interface Gossip<Message>;

	uses interface LocalTime<TMilli>;

	uses interface Timer<TMilli> as WaitTimer;

	uses interface MetricLogging;
	uses interface MetricHelpers;

	uses interface Cache<Message> as SentCache;
	uses interface Dictionary<Message, gossip_message_info_t> as MessageDict;
}

implementation
{
	error_t remove_message(const Message* msg)
	{
		if (!call MessageDict.remove(*msg))
		{
			ERROR_OCCURRED(ERROR_UNKNOWN, "Tried to remove a message, not found.\n");
		}

		if (call MessageDict.count() == 0)
		{
			call WaitTimer.stop();
		}

		return SUCCESS;
	}

	void remove_expired_messages(void)
	{
		const uint32_t current_time = call LocalTime.get();

		const Message* iter_begin = call MessageDict.beginKeysReverse();
		const Message* iter_end = call MessageDict.endKeysReverse();
		const Message* iter;

		//simdbg("stdout", "Removing expired messages start %u\n", call MessageDict.count());

		for (iter = iter_begin; iter != iter_end; --iter)
		{
			const gossip_message_info_t* value = call MessageDict.get_from_iter(iter);

			if (value->insert_time + (2*wait_period) >= current_time)
			{
				call SentCache.insert(*iter);
				remove_message(iter);
			}
		}

		//simdbg("stdout", "Removing expired messages end %u\n", call MessageDict.count());
	}

	command error_t Gossip.receive(Message* msg)
	{
		const uint32_t current_time = call LocalTime.get();

		gossip_message_info_t* value = call MessageDict.get(*msg);
		if (value != NULL)
		{
			value->seen_count += 1;
		}
		else if (!call SentCache.lookup(*msg))
		{
			bool result;

			const gossip_message_info_t local_value = { current_time, 1 };

			result = call MessageDict.put(*msg, local_value);

			if (!result)
			{
				ERROR_OCCURRED(ERROR_QUEUE_FULL, "No gossip queue space available for another message.\n");
				return ENOMEM;
			}

			if (!call WaitTimer.isRunning())
			{
				call WaitTimer.startOneShot(wait_period);
			}
		}

		return SUCCESS;
	}

	event void WaitTimer.fired()
	{
		const uint32_t current_time = call LocalTime.get();
		uint32_t min_insert_time = UINT32_MAX;

		const Message* iter_begin = call MessageDict.beginKeys();
		const Message* iter_end = call MessageDict.endKeys();
		const Message* iter;

		for (iter = iter_begin; iter != iter_end; ++iter)
		{
			gossip_message_info_t* value = call MessageDict.get_from_iter(iter);

			if (value->insert_time + wait_period >= current_time && value->seen_count == 1)
			{
				signal Gossip.send_message(iter);

				call SentCache.insert(*iter);

				remove_message(iter);

				break;
			}
		}

		remove_expired_messages();

		// Restart the timer potentially

		iter_begin = call MessageDict.beginKeys();
		iter_end = call MessageDict.endKeys();

		for (iter = iter_begin; iter != iter_end; ++iter)
		{
			const gossip_message_info_t* value = call MessageDict.get_from_iter(iter);

			min_insert_time = min(min_insert_time, value->insert_time);
		}

		if (min_insert_time != UINT32_MAX)
		{
			const uint32_t diff = call LocalTime.get() - min_insert_time;

			if (diff < wait_period)
			{
				call WaitTimer.startOneShot(diff);
			}
			else
			{
				call WaitTimer.startOneShot(wait_period);
			}
		}
	}
}
