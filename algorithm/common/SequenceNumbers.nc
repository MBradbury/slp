#include "SequenceNumber.h"

interface SequenceNumbers
{
	command SequenceNumber* get(am_addr_t address);
	command SequenceNumber next(am_addr_t address);
	command void increment(am_addr_t address);
	command bool before(am_addr_t address, SequenceNumber other);
	command void update(am_addr_t address, SequenceNumber other);

	command uint16_t max_size();
	command uint16_t count();
}
