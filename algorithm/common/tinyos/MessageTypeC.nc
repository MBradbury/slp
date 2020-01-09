
generic configuration MessageTypeC(uint8_t maximum_message_types)
{
	provides interface MessageType;

	uses interface MetricLogging;
}
implementation
{
	components new MessageTypeP(maximum_message_types);
	MessageType = MessageTypeP;
	MessageTypeP.MetricLogging = MetricLogging;

	components MainC;
	MainC.SoftwareInit -> MessageTypeP;	
}
