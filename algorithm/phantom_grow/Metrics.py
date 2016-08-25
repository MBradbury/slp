from __future__ import print_function, division

from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):
    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

        self.register('Metric-PATH-END', self.process_PATH_END)

        self._paths_reached_end = []

    def _process_PATH_END(self, d_or_e, node_id, time, detail):
        (proximate_source_id, ultimate_source_id, sequence_number, hop_count) = detail.split(',')

        ord_ultimate_source_id, top_ultimate_source_id = self._process_node_id(ultimate_source_id)
        sequence_number = int(sequence_number)

        self._paths_reached_end.append((top_ultimate_source_id, sequence_number))

    def paths_reached_end(self):
        return len(self._paths_reached_end) / len(self.normal_sent_time)

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["AwaySent"]               = lambda x: x.number_sent("Away")
        d["BeaconSent"]             = lambda x: x.number_sent("Beacon")
        d["PathsReachedEnd"]        = lambda x: x.paths_reached_end()

        return d
