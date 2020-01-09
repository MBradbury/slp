#include "SequenceNumber.h"

interface SequenceNumbers
{
	command SequenceNumber* get(am_addr_t address);
	command SequenceNumber next(am_addr_t address);
	command void increment(am_addr_t address);
	command bool before(am_addr_t address, SequenceNumber other);
	command void update(am_addr_t address, SequenceNumber other);
	command bool before_and_update(am_addr_t address, SequenceNumber other);

	command uint16_t max_size();
	command uint16_t count();

	command SequenceNumber* begin();
	command SequenceNumber* end();

	command am_addr_t* beginKeys();
	command am_addr_t* endKeys();
}
