#include "Constants.h"

module ObjectDetectorImplP
{
	provides interface ObjectDetector;

	uses interface Timer<TMilli> as DetectionTimer;
	uses interface Timer<TMilli> as ExpireTimer;
}
implementation
{
	bool detected = FALSE;

	uint32_t current_index = 0; 


	typedef struct {
		uint32_t from;
		uint32_t to;
	} slp_period_t;

	
	const am_addr_t indexes[] = SOURCE_DETECTED_INDEXES;
	const slp_period_t periods[][SOURCE_DETECTED_NUM_NODES] = SOURCE_DETECTED_PERIODS;
	const uint32_t periods_lengths[] = SOURCE_DETECTED_PERIODS_LENGTHS;

	bool get_index_from_address(am_addr_t id, uint32_t* idx)
	{
		unsigned int i = 0;
		for (i = 0; i != ARRAY_LENGTH(indexes); ++i)
		{
			if (indexes[i] == id)
			{
				*idx = i;
				return TRUE;
			}
		}

		return FALSE;
	}

	bool get_periods_active(am_addr_t id, const slp_period_t** period, uint32_t* length)
	{
		uint32_t idx;
		if (get_index_from_address(id, &idx))
		{
			*period = periods[idx];
			*length = periods_lengths[idx];
			return TRUE;
		}
		else
		{
			*period = NULL;
			*length = 0;
			return FALSE;
		}
	}

	void start_next_timer()
	{
		const slp_period_t* period;
		uint32_t length;

		if (get_periods_active(TOS_NODE_ID, &period, &length) && current_index < length)
		{
			dbgverbose("stdout", "Starting a detection timer for %u.\n", period[current_index].from);

			call DetectionTimer.startOneShotAt(period[current_index].from, 0);
		}
	}

	command void ObjectDetector.start()
	{
		start_next_timer();
	}

	command void ObjectDetector.stop()
	{
		detected = FALSE;
		signal ObjectDetector.stoppedDetecting();
	}
	
	default event void ObjectDetector.detect()
	{
	}
	default event void ObjectDetector.stoppedDetecting()
	{
	}

	command bool ObjectDetector.isDetected()
	{
		return detected;
	}

	event void DetectionTimer.fired()
	{
		const slp_period_t* period;
		uint32_t length;

		dbgverbose("stdout", "Detected an object.\n");

		signal ObjectDetector.detect();

		if (get_periods_active(TOS_NODE_ID, &period, &length) && current_index < length)
		{
			// Don't start the expiry timer if this detection
			// is to continue forever
			if (period[current_index].to != (uint32_t)-1)
			{
				const uint32_t expire_at = period[current_index].to - period[current_index].from;

				dbgverbose("stdout", "Starting an expiration timer in %ums.\n", expire_at);

				call ExpireTimer.startOneShot(expire_at);
			}
		}
	}

	event void ExpireTimer.fired()
	{
		dbgverbose("stdout", "Stopped detecting an object.\n");

		call ObjectDetector.stop();

		++current_index;

		start_next_timer();
	}
}
