generic configuration SetC(typedef Value, uint16_t MAX_SIZE)
{
	provides interface Set<Value>;

	uses interface Compare<Value>;
}
implementation
{
	components new SetP(Value, MAX_SIZE);
	Set = SetP;
	SetP.Compare = Compare;

	components MainC;
	MainC.SoftwareInit -> SetP;
}