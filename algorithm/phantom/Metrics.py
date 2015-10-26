from __future__ import division

from simulator.MetricsCommon import MetricsCommon

from numpy import mean

class Metrics(MetricsCommon):
    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

        self.register('Metric-COMMUNICATE', self.process_COMMUNICATE)

        # Normal nodes becoming the source, or source nodes becoming normal
        self.register('Metric-SOURCE_CHANGE', self.process_SOURCE_CHANGE)

        self.register('Metric-PATH-END', self._process_PATH_END)
        self.register('Metric-SOURCE_DROPPED', self._process_SOURCE_DROPPED)
        self.register('Metric-PATH_DROPPED', self._process_PATH_DROPPED)

        self._paths_reached_end = []
        self._source_dropped = []
        self._path_dropped = []

    def _process_PATH_END(self, line):
        (time, node_id, proximate_source_id, ultimate_source_id, sequence_number, hop_count) = line.split(',')

        self._paths_reached_end.append((ultimate_source_id, sequence_number))

    def _process_SOURCE_DROPPED(self, line):
        (time, node_id, sequence_number) = line.split(',')

        time = int(time)

        self._source_dropped.append(time)

    def _process_PATH_DROPPED(self, line):
        (time, node_id, sequence_number, source_distance) = line.split(',')

        source_distance = int(source_distance)

        self._path_dropped.append(source_distance)

    def paths_reached_end(self):
        return len(self._paths_reached_end) / len(self.normal_sent_time)

    def source_dropped(self):
        return len(self._source_dropped) / (len(self._source_dropped) + len(self.normal_sent_time))

    def path_dropped(self):
        return len(self._path_dropped) / len(self.normal_sent_time)

    def path_dropped_average_length(self):
        return 0 if len(self._path_dropped) == 0 else mean(self._path_dropped)

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["AwaySent"]               = lambda x: x.number_sent("Away")
        d["BeaconSent"]             = lambda x: x.number_sent("Beacon")
        d["PathsReachedEnd"]        = lambda x: x.paths_reached_end()
        d["SourceDropped"]          = lambda x: x.source_dropped()
        d["PathDropped"]            = lambda x: x.path_dropped()
        d["PathDroppedLength"]      = lambda x: x.path_dropped_average_length()

        return d
