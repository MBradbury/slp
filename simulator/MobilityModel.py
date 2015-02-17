from collections import OrderedDict

from data.restricted_eval import restricted_eval

class MobilityModel(object):
    def __init__(self):
        pass

    def setup(self, configuration, times):
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
    def __init__(self):
        super(StationaryMobilityModel, self).__init__()

    def setup(self, configuration):
        times = OrderedDict()
        times[configuration.source_id] = [(0, float('inf'))]

        super(StationaryMobilityModel, self).setup(configuration, times)

    def __repr__(self):
        return "StationaryMobilityModel()"

class RandomWalkMobilityModel(MobilityModel):
    def __init__(self, max_time, duration):
        self.max_time = max_time

        # Duration is the length for which a node will act as a source node.
        self.duration = duration

        super(RandomWalkMobilityModel, self).__init__()

    def setup(self, configuration):

        raise NotImplemented()

        # TODO: Use configuration.connectivity_matrix to choose which node
        # to move the source to after the duration

        super(RandomWalkMobilityModel, self).__init__(configuration)

    def __repr__(self):
        return "RandomWalkMobilityModel(max_time={}, duration={})".format(
            self.max_time, self.duration)


class TowardsSinkMobilityModel(MobilityModel):
    def __init__(self, duration):
        self.duration = duration

    def setup(self, configuration):
        path = configuration.shortest_path(configuration.source_id, configuration.sink_id)

        times = OrderedDict()

        current_time = 0

        for (i, node) in enumerate(path):
            end_time = current_time + self.duration if (i + 1) != len(path) else float('inf')

            times[node] = [(current_time, end_time)]

            current_time += self.duration

        super(TowardsSinkMobilityModel, self).setup(configuration, times)

    def __repr__(self):
        return "TowardsSinkMobilityModel(duration={})".format(self.duration)

def models():
    """A list of the names of the available models."""
    return [cls for cls in MobilityModel.__subclasses__()]

def eval_input(source):
    result = restricted_eval(source, models())

    if isinstance(result, MobilityModel):
        return result
    else:
        raise RuntimeError("The source ({}) is not valid.".format(source))
