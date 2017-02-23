generic configuration CircularBufferC(typedef value_t, uint8_t BUFFER_SIZE)
{
	provides interface Cache<value_t>;
}
implementation
{
	components new CircularBufferP(value_t, BUFFER_SIZE);
	Cache = CircularBufferP;

	components MainC;
	MainC.SoftwareInit -> CircularBufferP;	
}
