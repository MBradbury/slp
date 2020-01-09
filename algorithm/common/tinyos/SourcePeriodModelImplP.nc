#include "Common.h"

// Arrays can't have a Zero length
#if PERIOD_TIMES_LEN > 0

typedef struct {
	uint32_t end;
	uint32_t period;
} local_end_period_t;

const local_end_period_t times[PERIOD_TIMES_LEN] = PERIOD_TIMES_MS;

#endif

const uint32_t else_time = PERIOD_ELSE_TIME_MS;

module SourcePeriodModelImplP
{
	provides interface SourcePeriodModel;

	uses interface SourcePeriodConverter;

	uses interface Timer<TMilli> as EventTimer;
}
implementation
{
	default command uint32_t SourcePeriodConverter.convert(uint32_t period)
	{
		return period;
	}

	command uint32_t SourcePeriodModel.get()
	{
#if PERIOD_TIMES_LEN > 0
		unsigned int i = 0;

		uint32_t period = UINT32_MAX;

		const uint32_t current_time = call EventTimer.getNow();

		//simdbgverbose("stdout", "Called get_source_period current_time=%" PRIu32 " #times=%u\n",
		//	current_time, PERIOD_TIMES_LEN);

		for (i = 0; i != PERIOD_TIMES_LEN; ++i)
		{
			//simdbgverbose("stdout", "i=%u current_time=%u end=%u period=%u\n",
			//	i, current_time, times[i].end, times[i].period);

			if (current_time < times[i].end)
			{
				period = times[i].period;
				break;
			}
		}

		if (i == PERIOD_TIMES_LEN)
		{
			period = else_time;
		}
#else
		const uint32_t period = else_time;
#endif

		//simdbgverbose("stdout", "Providing source period %" PRIu32 " at time=%" PRIu32 "\n",
		//	period, current_time);

		return call SourcePeriodConverter.convert(period);
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
