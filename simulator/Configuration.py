
class Configuration:
	def __init__(self, topology, sourceId, sinkId):
		self.topology = topology
		self.sinkId = sinkId
		self.sourceId = sourceId

		if self.sinkId >= len(self.topology.nodes):
			raise Exception("There are not enough nodes ({}) to have a sink id of {}".format(len(self.topology.nodes), self.sinkId))

		if self.sourceId >= len(self.topology.nodes):
			raise Exception("There are not enough nodes ({}) to have a source id of {}".format(len(self.topology.nodes), self.source))
