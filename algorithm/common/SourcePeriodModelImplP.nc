#include "Common.h"

module SourcePeriodModelImplP
{
	provides interface SourcePeriodModel;

	uses interface LocalTime<TMilli>;

	uses interface Timer<TMilli> as EventTimer;
}
implementation
{
	typedef struct {
		uint32_t end;
		uint32_t period;
	} local_end_period_t;

	const local_end_period_t times[] = PERIOD_TIMES_MS;
	const uint32_t else_time = PERIOD_ELSE_TIME_MS;

	command uint32_t SourcePeriodModel.get()
	{
		const uint32_t current_time = call LocalTime.get();

		const unsigned int times_length = ARRAY_LENGTH(times);

		unsigned int i;

		uint32_t period = -1;

		simdbgverbose("stdout", "Called get_source_period current_time=%" PRIu32 " #times=%u\n",
			current_time, times_length);

		for (i = 0; i != times_length; ++i)
		{
			//simdbgverbose("stdout", "i=%u current_time=%u end=%u period=%u\n",
			//	i, current_time, times[i].end, times[i].period);

			if (current_time < times[i].end)
			{
				period = times[i].period;
				break;
			}
		}

		if (i == times_length)
		{
			period = else_time;
		}

		simdbgverbose("stdout", "Providing source period %" PRIu32 " at time=%" PRIu32 "\n",
			period, current_time);

		return period;
	}

	command void SourcePeriodModel.startPeriodic()
	{
		call EventTimer.startOneShot(call SourcePeriodModel.get());
	}

	command void SourcePeriodModel.stop()
	{
		call EventTimer.stop();
	}

	event void EventTimer.fired()
	{
		call EventTimer.startOneShot(call SourcePeriodModel.get());

		signal SourcePeriodModel.fired();
	}
}
