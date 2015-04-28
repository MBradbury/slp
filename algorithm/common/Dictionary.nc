
interface Dictionary<Key, Value>
{
	command bool put(Key key, Value value);
	command Value* get(Key key);
	command Value get_or_default(Key key, Value default_value);

	command uint16_t count();

	command Value* begin();
	command Value* end();
}
