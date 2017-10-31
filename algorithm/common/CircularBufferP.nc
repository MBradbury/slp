generic module CircularBufferP(typedef value_t, uint8_t BUFFER_SIZE)
{
	provides interface Cache<value_t>;
	provides interface Init;

	uses interface Compare<value_t>;
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
			size++;
	}

	command bool Cache.lookup(value_t item)
	{
		uint8_t i;
		for (i = 0; i != size; ++i)
		{
			if (call Compare.equals(&values[i], &item))
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
