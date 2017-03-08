
interface Dictionary<Key, Value>
{
	command bool put(Key key, Value value);
	command Value* get(Key key);
	command Value* get_from_iter(const Key* iter);
	command Value get_or_default(Key key, Value default_value);
	command const Key* key_iter_from_key(Key key);
	command bool remove(Key key);

	command bool contains_key(Key key);

	command uint16_t count();
	command uint16_t max_size();

	command Value* begin();
	command Value* end();

	command const Key* beginKeys();
	command const Key* endKeys();

	command const Key* beginKeysReverse();
	command const Key* endKeysReverse();
}
