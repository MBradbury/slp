
class MobilityModel(object):
	def __init__(self, configuration, times):
		self.configuration = configuration
		self.active_times = times

		self._validate_times()

	def _validate_times(self, times):
		"""Checks if the list of time intervals is valid"""

		num_nodes = len(self.configuration.topology.nodes)

		for (node_id, intervals) in self.active_times:
			if node_id > num_nodes:
				raise RuntimeError("Invalid node id {}.".format(node_id))

class StationaryMobilityModel(MobilityModel):
	def __init__(self, configuration):

		times = { configuration.source_id: [(0, float('inf')] }

		super(StationaryMobility, self).__init__(configuration, times)

class RandomWalkMobilityModel(MobilityModel):
	def __init__(self, configuration, duration):
		super(RandomWalkMobilityModel, self).__init__(configuration)

		# Duration is the length for which a node will act as a source node.
		self.duration = duration

		# TODO: Use configuration.connectivity_matrix to choose which node
		# to move the source to after the duration


class TowardsSinkMobilityModel(MobilityModel):
	def __init__(self, configuration):
		super(TowardsSinkMobilityModel, self).__init__(configuration)

		# TODO: Use scipy to find shortest path using configuration.connectivity_matrix

