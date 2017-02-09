
generic module DictionaryP(typedef Key, typedef Value, uint16_t MAX_SIZE)
{
  provides interface Dictionary<Key, Value>;

  uses interface Compare<Key>;
}

implementation
{
	Key keys[MAX_SIZE];
	Value values[MAX_SIZE];
	uint16_t count = 0;

	command uint16_t Dictionary.max_size()
	{
		return MAX_SIZE;
	}

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

	command const Key* Dictionary.beginKeys()
	{
		return keys;
	}

	command const Key* Dictionary.endKeys()
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

	command bool Dictionary.remove(Key key)
	{
		uint16_t i;

		for (i = 0; i != count; ++i)
		{
			if (call Compare.equals(&keys[i], &key))
			{
				break;
			}
		}

		// No key in dictionary
		if (i == count)
		{
			return FALSE;
		}

		memmove(&keys[i], &keys[i+1], (MAX_SIZE-i-1)*sizeof(*keys));
		memmove(&values[i], &values[i+1], (MAX_SIZE-i-1)*sizeof(*values));

		count -= 1;

		return TRUE;
	}

	command Value* Dictionary.get(Key key)
	{
		uint16_t i;
		for (i = 0; i != count; ++i)
		{
			if (call Compare.equals(&keys[i], &key))
			{
				return &values[i];
			}
		}

		return NULL;
	}

	command Value* Dictionary.get_from_iter(const Key* iter)
	{
		ptrdiff_t i = iter - call Dictionary.beginKeys();
		return &values[i];
	}

	command Value Dictionary.get_or_default(Key key, Value default_value)
	{
		Value* stored_value = call Dictionary.get(key);

		return stored_value == NULL ? default_value : *stored_value;
	}

	command bool Dictionary.contains_key(Key key)
	{
		return call Dictionary.get(key) != NULL;
	}
}
