
generic module DictionaryP(typedef Key, typedef Value, uint16_t MAX_SIZE)
{
  provides interface Dictionary<Key, Value>;
}

implementation
{
	Key keys[MAX_SIZE];
	Value values[MAX_SIZE];
	uint16_t count = 0;

	command uint16_t Dictionary.count()
	{
		return count;
	}

	command Value* Dictionary.begin()
	{
		return values;
	}

	command Value* Dictionary.end()
	{
		return values + count;
	}

	command Key* Dictionary.beginKeys()
	{
		return keys;
	}

	command Key* Dictionary.endKeys()
	{
		return keys + count;
	}

	command bool Dictionary.put(Key key, Value value)
	{
		Value* stored_value = call Dictionary.get(key);

		if (stored_value == NULL)
		{
			if (count < MAX_SIZE)
			{
				keys[count] = key;
				stored_value = &values[count];
				count += 1;
			}
			else
			{
				return FALSE;
			}
		}

		assert(stored_value != NULL);

		*stored_value = value;

		return TRUE;
	}

	command Value* Dictionary.get(Key key)
	{
		int16_t i;
		for (i = 0; i != count; ++i)
		{
			if (memcmp(&keys[i], &key, sizeof(Key)) == 0)
			{
				return &values[i];
			}
		}

		return NULL;
	}

	command Value Dictionary.get_or_default(Key key, Value default_value)
	{
		Value* stored_value = call Dictionary.get(key);

		return stored_value == NULL ? default_value : *stored_value;
	}
}
