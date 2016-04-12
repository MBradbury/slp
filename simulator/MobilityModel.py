from collections import OrderedDict

from data.restricted_eval import restricted_eval

import math

class MobilityModel(object):
    def __init__(self):
        self.configuration = None
        self.active_times = None

    def setup(self, configuration):
        raise NotImplementedError()

    def _setup_impl(self, configuration, times):
        self.configuration = configuration
        self.active_times = times

        self._validate_times()

    def _validate_times(self):
        """Checks if the list of time intervals is valid"""

        num_nodes = len(self.configuration.topology.nodes)

        for (node_id, intervals) in self.active_times.items():
            if node_id > num_nodes:
                raise RuntimeError("Invalid node id {}.".format(node_id))

            if node_id == self.configuration.sink_id:
                raise RuntimeError("The source node cannot move onto the sink as it cannot detect it")

    def build_arguments(self):
        build_arguments = {}

        def to_tinyos_format(time):
            if math.isinf(time):
                return "-1"
            else:
                return "{}U".format(int(time * 1000))

        indexes = []
        periods = []
        periods_lengths = []

        for (node_id, intervals) in self.active_times.items():

            indexes.append("{}U".format(node_id))

            period = [
                "{{{}, {}}}".format(to_tinyos_format(begin), to_tinyos_format(end))
                for (begin, end)
                in intervals
            ]

            periods.append("{ " + ", ".join(period) + " }")

            periods_lengths.append("{}U".format(len(period)))

        build_arguments["SOURCE_DETECTED_INDEXES"] = "{ " + ", ".join(indexes) + " }"
        build_arguments["SOURCE_DETECTED_PERIODS"] = "{ " + ", ".join(periods) + " }"
        build_arguments["SOURCE_DETECTED_PERIODS_LENGTHS"] = "{ " + ", ".join(periods_lengths) + " }"
        build_arguments["SOURCE_DETECTED_NUM_NODES"] = len(indexes)

        return build_arguments

    def __str__(self):
        return type(self).__name__ + "()"

class StationaryMobilityModel(MobilityModel):
    def __init__(self):
        super(StationaryMobilityModel, self).__init__()

    def setup(self, configuration):
        times = OrderedDict()

        for source_id in configuration.source_ids:
            times[source_id] = [(0, float('inf'))]

        self._setup_impl(configuration, times)

class RandomWalkMobilityModel(MobilityModel):
    def __init__(self, max_time, duration):
        # There needs to be a finite length to the random walk!
        self.max_time = max_time

        # Duration is the length for which a node will act as a source node.
        self.duration = duration

        super(RandomWalkMobilityModel, self).__init__()

    def setup(self, configuration):
        # TODO: Use configuration.connectivity_matrix to choose which node
        # to move the source to after the duration
        raise NotImplementedError()

    def __str__(self):
        return type(self).__name__ + "(max_time={}, duration={})".format(self.max_time, self.duration)


class TowardsSinkMobilityModel(MobilityModel):
    def __init__(self, duration):
        super(TowardsSinkMobilityModel, self).__init__()
        self.duration = duration

    def setup(self, configuration):
        times = OrderedDict()

        for source_id in configuration.source_ids:
            path = configuration.shortest_path(source_id, configuration.sink_id)

            # Remove the last element from the list as the sink cannot become a source
            path = path[:-1]

            current_time = 0

            for (i, node) in enumerate(path):
                end_time = current_time + self.duration if (i + 1) != len(path) else float('inf')

                if node not in times:
                    times[node] = [(current_time, end_time)]
                else:
                    times[node].append( (current_time, end_time) )

                current_time += self.duration

        self._setup_impl(configuration, times)

    def __str__(self):
        return type(self).__name__ + "(duration={})".format(self.duration)

def models():
    """A list of the names of the available models."""
    return [cls for cls in MobilityModel.__subclasses__()]

def eval_input(source):
    result = restricted_eval(source, models())

    if result in models():
        raise RuntimeError("The source mobility model ({}) is not valid. (Did you forget the brackets after the name?)".format(source))

    if not isinstance(result, MobilityModel):
        raise RuntimeError("The source mobility model ({}) is not valid.".format(source))

    return result
