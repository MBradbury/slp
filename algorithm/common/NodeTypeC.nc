
generic configuration NodeTypeC(uint8_t maximum_node_types)
{
	provides interface NodeType;

	uses interface MetricLogging;
}
implementation
{
	components new NodeTypeP(maximum_node_types);
	NodeType = NodeTypeP;
	NodeTypeP.MetricLogging = MetricLogging;

	components MainC;
	MainC.SoftwareInit -> NodeTypeP;	
}
