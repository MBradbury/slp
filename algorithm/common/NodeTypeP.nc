
generic configuration NodeTypeP(uint8_t maximum_size)
{
	provides interface NodeType;

	uses interface MetricLogging;
}
implementation
{
	components new NodeTypeImplP(maximum_size) as App;

	App.NodeType = NodeType;
	App.MetricLogging = MetricLogging;
}
