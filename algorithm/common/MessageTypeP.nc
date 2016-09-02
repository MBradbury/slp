
generic configuration MessageTypeP(uint8_t maximum_size)
{
	provides interface MessageType;

	uses interface MetricLogging;
}
implementation
{
	components new MessageTypeImplP(maximum_size) as App;

	App.MessageType = MessageType;
	App.MetricLogging = MetricLogging;
}
