from __future__ import print_function, division

import numpy as np

from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):
    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

        self.register('M-PE', self._process_PATH_END)
        self.register('M-SD', self._process_SOURCE_DROPPED)
        self.register('M-PD', self._process_PATH_DROPPED)

        self._paths_reached_end = []
        self._source_dropped = []
        self._path_dropped = []

    def _process_PATH_END(self, d_or_e, node_id, time, detail):
        (proximate_source_id, ultimate_source_id, sequence_number, hop_count) = detail.split(',')

        ord_ultimate_source_id, top_ultimate_source_id = self._process_node_id(ultimate_source_id)
        sequence_number = int(sequence_number)

        self._paths_reached_end.append((top_ultimate_source_id, sequence_number))

    def _process_SOURCE_DROPPED(self, d_or_e, node_id, time, detail):
        (sequence_number,) = detail.split(',')

        time = float(time)

        self._source_dropped.append(time)

    def _process_PATH_DROPPED(self, d_or_e, node_id, time, detail):
        (sequence_number, source_distance) = detail.split(',')

        source_distance = int(source_distance)

        self._path_dropped.append(source_distance)

    def paths_reached_end(self):
        return len(self._paths_reached_end) / self.num_normal_sent_if_finished()

    def source_dropped(self):
        return len(self._source_dropped) / (len(self._source_dropped) + self.num_normal_sent_if_finished())

    def path_dropped(self):
        return len(self._path_dropped) / self.num_normal_sent_if_finished()

    def path_dropped_average_length(self):
        return 0 if len(self._path_dropped) == 0 else np.mean(self._path_dropped)

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
