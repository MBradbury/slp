generic module CircularBufferP(typedef value_t, uint8_t BUFFER_SIZE)
{
	provides interface Cache<value_t>;
	provides interface Init;
}
implementation
{
	value_t values[BUFFER_SIZE];
	uint8_t size;

	command error_t Init.init()
	{
		size = 0;
		return SUCCESS;
	}

	command void Cache.insert(value_t item)
	{
		const uint8_t idx = (size + 1) % BUFFER_SIZE;

		values[idx] = item;

		if (size != BUFFER_SIZE)
			size += 1;
	}

	command bool Cache.lookup(value_t item)
	{
		uint8_t i;
		for (i = 0; i != size; ++i)
		{
			if (memcmp(&values[i], &item, sizeof(value_t)) == 0)
			{
				return TRUE;
			}
		}
		return FALSE;
	}
   
	command void Cache.flush()
	{
		size = 0;
	}
}
