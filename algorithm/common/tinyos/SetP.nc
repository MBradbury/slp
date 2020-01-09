
generic module SetP(typedef Value, uint16_t MAX_SIZE)
{
  provides interface Set<Value>;
  provides interface Init;

  uses interface Compare<Value>;
}

implementation
{
	Value values[MAX_SIZE];
	uint16_t count;

	command error_t Init.init()
	{
		count = 0;
		return SUCCESS;
	}

	command uint16_t Set.count()
	{
		return count;
	}

	command const Value* Set.begin()
	{
		return values;
	}

	command const Value* Set.end()
	{
		return values + count;
	}

	command bool Set.put(Value value)
	{
		if (!call Set.contains(value))
		{
			if (count < MAX_SIZE)
			{
				values[count] = value;
				count += 1;
			}
			else
			{
				return FALSE;
			}
		}

		return TRUE;
	}

	uint16_t indexof_value(Value value)
	{
		uint16_t i;

		for (i = 0; i != count; ++i)
		{
			if (call Compare.equals(&values[i], &value))
			{
				break;
			}
		}

		return i;
	}

	command bool Set.remove(Value value)
	{
		const uint16_t i = indexof_value(value);

		// No key in Set
		if (i == count)
		{
			return FALSE;
		}

		memmove(&values[i], &values[i+1], (MAX_SIZE-i-1)*sizeof(*values));

		count -= 1;

		return TRUE;
	}

	command bool Set.contains(Value value)
	{
		const uint16_t i = indexof_value(value);

		return i != count;
	}
}
