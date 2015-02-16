
class MobilityModel(object):
	def __init__(self, configuration, times):
		self.configuration = configuration
		self.active_times = times

		self._validate_times()

	def _validate_times(self):
		"""Checks if the list of time intervals is valid"""

		num_nodes = len(self.configuration.topology.nodes)

		for (node_id, intervals) in self.active_times.items():
			if node_id > num_nodes:
				raise RuntimeError("Invalid node id {}.".format(node_id))

class StationaryMobilityModel(MobilityModel):
	def __init__(self, configuration):

		times = { configuration.source_id: [(0, float('inf'))] }

		super(StationaryMobilityModel, self).__init__(configuration, times)

class RandomWalkMobilityModel(MobilityModel):
	def __init__(self, configuration, max_time, duration=1):

		# Duration is the length for which a node will act as a source node.
		self.duration = duration

		# TODO: Use configuration.connectivity_matrix to choose which node
		# to move the source to after the duration

		super(RandomWalkMobilityModel, self).__init__(configuration)


class TowardsSinkMobilityModel(MobilityModel):
	def __init__(self, configuration, duration=1):
		path = configuration.shortest_path(configuration.source_id, configuration.sink_id)

		times = {}

		current_time = 0

		for (i, node) in enumerate(path):
			end_time = current_time + duration if (i + 1) != len(path) else float('inf')

			times[node] = [(current_time, end_time)]

			current_time += duration

		super(TowardsSinkMobilityModel, self).__init__(configuration, times)
