#include "SequenceNumber.h"

#include "Common.h"

generic module SequenceNumbersP(uint16_t MAX_SIZE)
{
	provides interface SequenceNumbers;
	provides interface Init;
}

implementation
{
	SequenceNumber sequence_numbers[MAX_SIZE];
	am_addr_t sources[MAX_SIZE];
	uint16_t sources_count;

	command error_t Init.init()
	{
		sources_count = 0;
		return SUCCESS;
	}

	command uint16_t SequenceNumbers.max_size()
	{
		return MAX_SIZE;
	}

	command uint16_t SequenceNumbers.count()
	{
		return sources_count;
	}

	SequenceNumber* find(am_addr_t address)
	{
		uint16_t i;
		for (i = 0; i != sources_count; ++i)
		{
			if (sources[i] == address)
			{
				return &sequence_numbers[i];
			}
		}

		return (SequenceNumber*)NULL;
	}

	SequenceNumber* find_or_add(am_addr_t address)
	{
		SequenceNumber* result = find(address);

		if (result == NULL)
		{
			if (sources_count < MAX_SIZE)
			{
				sources[sources_count] = address;
				result = &sequence_numbers[sources_count];
				sequence_number_init(result);
				sources_count += 1;
			}
		}

		return result;
	}

	command SequenceNumber* SequenceNumbers.get(am_addr_t address)
	{
		return find_or_add(address);
	}

	command SequenceNumber SequenceNumbers.next(am_addr_t address)
	{
		const SequenceNumber* result = find_or_add(address);

#if SLP_VERBOSE_DEBUG
		assert(result != NULL);
#endif

		return sequence_number_next(result);
	}

	command void SequenceNumbers.increment(am_addr_t address)
	{
		SequenceNumber* result = find_or_add(address);

#if SLP_VERBOSE_DEBUG
		assert(result != NULL);
#endif

		sequence_number_increment(result);
	}

	command bool SequenceNumbers.before(am_addr_t address, SequenceNumber other)
	{
		const SequenceNumber* result = find_or_add(address);

#if SLP_VERBOSE_DEBUG
		assert(result != NULL);
#endif

		return sequence_number_before(result, other);
	}

	command void SequenceNumbers.update(am_addr_t address, SequenceNumber other)
	{
		SequenceNumber* result = find_or_add(address);

#if SLP_VERBOSE_DEBUG
		assert(result != NULL);
#endif

		sequence_number_update(result, other);
	}

	command am_addr_t* SequenceNumbers.beginKeys()
	{
		return sources;
	}

	command am_addr_t* SequenceNumbers.endKeys()
	{
		return sources + sources_count;
	}

	command SequenceNumber* SequenceNumbers.begin()
	{
		return sequence_numbers;
	}

	command SequenceNumber* SequenceNumbers.end()
	{
		return sequence_numbers + sources_count;
	}
}
