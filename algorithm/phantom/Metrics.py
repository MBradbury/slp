from collections import Counter
import enum

import numpy as np

from simulator.MetricsCommon import MetricsCommon

class MessageDirection(enum.IntFlag):
    UNKNOWN = 0
    CLOSER = (1 << 0)
    FURTHER = (1 << 1)

class Metrics(MetricsCommon):
    METRIC_GENERIC_PATH_END = 3001
    METRIC_GENERIC_SOURCE_DROPPED = 3002
    METRIC_GENERIC_PATH_DROPPED = 3003
    METRIC_GENERIC_DIRECTION = 3004

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.register_generic(self.METRIC_GENERIC_PATH_END, self._process_PATH_END)
        self.register_generic(self.METRIC_GENERIC_SOURCE_DROPPED, self._process_SOURCE_DROPPED)
        self.register_generic(self.METRIC_GENERIC_PATH_DROPPED, self._process_PATH_DROPPED)
        self.register_generic(self.METRIC_GENERIC_DIRECTION, self._process_PATH_DIRECTION)

        self._paths_reached_end = []
        self._source_dropped = []
        self._path_dropped = []
        self._path_direction = Counter()

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

    def _process_PATH_DIRECTION(self, d_or_e, node_id, time, detail):
        (sequence_number, direction) = detail.split(',')

        direction = MessageDirection(int(direction))

        self._path_direction[direction] += 1

    def paths_reached_end(self):
        return len(self._paths_reached_end) / self.num_normal_sent_if_finished()

    def source_dropped(self):
        return len(self._source_dropped) / (len(self._source_dropped) + self.num_normal_sent_if_finished())

    def path_dropped(self):
        return len(self._path_dropped) / self.num_normal_sent_if_finished()

    def path_dropped_average_length(self):
        return 0 if len(self._path_dropped) == 0 else np.mean(self._path_dropped)

    def path_direction_bias(self):
        return {k.name: v for (k, v)  in self._path_direction.items()}

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["AwaySent"]               = lambda x: x.number_sent("Away")
        d["BeaconSent"]             = lambda x: x.number_sent("Beacon")
        d["PathsReachedEnd"]        = lambda x: x.paths_reached_end()
        d["SourceDropped"]          = lambda x: x.source_dropped()
        d["PathDropped"]            = lambda x: x.path_dropped()
        d["PathDroppedLength"]      = lambda x: x.path_dropped_average_length()
        d["PathDirectionBias"]      = lambda x: x.path_direction_bias()

        return d
