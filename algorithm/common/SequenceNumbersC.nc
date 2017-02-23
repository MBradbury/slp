generic configuration SequenceNumbersC(uint16_t MAX_SIZE)
{
	provides interface SequenceNumbers;
}
implementation
{
	components new SequenceNumbersP(MAX_SIZE);
	SequenceNumbers = SequenceNumbersP;

	components MainC;
	MainC.SoftwareInit -> SequenceNumbersP;	
}
