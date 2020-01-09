generic configuration CircularBufferC(typedef value_t, uint8_t BUFFER_SIZE)
{
	provides interface Cache<value_t>;

	uses interface Compare<value_t>;
}
implementation
{
	components new CircularBufferP(value_t, BUFFER_SIZE);
	Cache = CircularBufferP;
	CircularBufferP.Compare = Compare;

	components MainC;
	MainC.SoftwareInit -> CircularBufferP;	
}
