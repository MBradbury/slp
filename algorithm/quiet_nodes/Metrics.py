from __future__ import print_function, division

import numpy as np

from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):
    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

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
