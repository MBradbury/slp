
module ObjectDetectorImplP
{
	provides interface ObjectDetector;

	uses interface Timer<TMilli> as DetectionTimer;
	uses interface Timer<TMilli> as ExpireTimer;
}
implementation
{
	bool detected = FALSE;

	uint32_t additional_delay = 0;

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
		unsigned int i, end;
		for (i = 0, end = ARRAY_LENGTH(indexes); i != end; ++i)
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

	void start_next_timer(void)
	{
		const slp_period_t* period;
		uint32_t length;

		if (get_periods_active(TOS_NODE_ID, &period, &length) && current_index < length)
		{
			simdbgverbose("stdout", "Starting a detection timer for %u.\n", period[current_index].from);

			call DetectionTimer.startOneShotAt(additional_delay + period[current_index].from, 0);
		}
	}

	command void ObjectDetector.start()
	{
		additional_delay = 0;
		start_next_timer();
	}

	command void ObjectDetector.start_later(uint32_t delay)
	{
		additional_delay = delay;
		start_next_timer();
	}

	command void ObjectDetector.stop()
	{
		detected = FALSE;
		signal ObjectDetector.stoppedDetecting();
	}

	command bool ObjectDetector.isDetected()
	{
		return detected;
	}

	event void DetectionTimer.fired()
	{
		const slp_period_t* period;
		uint32_t length;

		simdbgverbose("stdout", "Detected an object.\n");

		detected = TRUE;

		if (get_periods_active(TOS_NODE_ID, &period, &length) && current_index < length)
		{
			// Don't start the expiry timer if this detection
			// is to continue forever
			if (period[current_index].to != (uint32_t)-1)
			{
				simdbgverbose("stdout", "Starting an expiration timer.\n");

				call ExpireTimer.startOneShotAt(
					additional_delay + period[current_index].from,
					additional_delay + period[current_index].to
				);
			}
		}

		signal ObjectDetector.detect();
	}

	event void ExpireTimer.fired()
	{
		simdbgverbose("stdout", "Stopped detecting an object.\n");

		call ObjectDetector.stop();

		++current_index;

		start_next_timer();
	}
}
