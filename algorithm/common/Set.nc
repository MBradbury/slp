
interface Set<Value>
{
	command bool put(Value value);
	command bool remove(Value value);

	command bool contains(Value value);

	command uint16_t count();

	command const Value* begin();
	command const Value* end();
}
