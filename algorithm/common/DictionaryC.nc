
generic configuration DictionaryC(typedef Key, typedef Value, uint16_t MAX_SIZE)
{
	provides interface Dictionary<Key, Value>;

	uses interface Compare<Key>;
}
implementation
{
	components new DictionaryP(Key, Value, MAX_SIZE);
	Dictionary = DictionaryP;
	DictionaryP.Compare = Compare;

	components MainC;
	MainC.SoftwareInit -> DictionaryP;	
}
