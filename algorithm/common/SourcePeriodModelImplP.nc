#include "Common.h"

typedef struct {
	uint32_t end;
	uint32_t period;
} local_end_period_t;

// Arrays can't have a Zero length
#if PERIOD_TIMES_LEN > 0
const local_end_period_t times[PERIOD_TIMES_LEN] = PERIOD_TIMES_MS;
#endif

const uint32_t else_time = PERIOD_ELSE_TIME_MS;

module SourcePeriodModelImplP
{
	provides interface SourcePeriodModel;

	uses interface SourcePeriodConverter;

	uses interface Timer<TMilli> as EventTimer;
	uses interface LocalTime<TMilli>;
}
implementation
{
	default command uint32_t SourcePeriodConverter.convert(uint32_t period)
	{
		return period;
	}

	command uint32_t SourcePeriodModel.get()
	{
		const uint32_t current_time = call LocalTime.get();

		unsigned int i = 0;

		uint32_t period = -1;

		simdbgverbose("stdout", "Called get_source_period current_time=%" PRIu32 " #times=%u\n",
			current_time, PERIOD_TIMES_LEN);

#if PERIOD_TIMES_LEN > 0
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
#endif

		if (i == PERIOD_TIMES_LEN)
		{
			period = else_time;
		}

		simdbgverbose("stdout", "Providing source period %" PRIu32 " at time=%" PRIu32 "\n",
			period, current_time);

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

	task void signal_source_period_model()
	{
		signal SourcePeriodModel.fired();
	}

	event void EventTimer.fired()
	{
		call EventTimer.startOneShot(call SourcePeriodModel.get());

		post signal_source_period_model();
	}
}
