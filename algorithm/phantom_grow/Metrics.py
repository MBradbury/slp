from __future__ import print_function, division

import sys

from simulator.Simulator import OutputCatcher
from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):
    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

        self.COMMUNICATE = OutputCatcher(self.process_COMMUNICATE)
        self.sim.tossim.addChannel('Metric-COMMUNICATE', self.COMMUNICATE.write)
        self.sim.add_output_processor(self.COMMUNICATE)

        # Normal nodes becoming the source, or source nodes becoming normal
        self.SOURCE_CHANGE = OutputCatcher(self.process_SOURCE_CHANGE)
        self.sim.tossim.addChannel('Metric-SOURCE_CHANGE', self.SOURCE_CHANGE.write)
        self.sim.add_output_processor(self.SOURCE_CHANGE)

        self.PATH_END = OutputCatcher(self.process_PATH_END)
        self.sim.tossim.addChannel('Metric-PATH-END', self.PATH_END.write)
        self.sim.add_output_processor(self.PATH_END)

        self._paths_reached_end = []

    def process_PATH_END(self, line):
        (time, node_id, proximate_source_id, ultimate_source_id, sequence_number, hop_count) = line.split(',')

        self._paths_reached_end.append((ultimate_source_id, sequence_number))

    def paths_reached_end(self):
        return len(self._paths_reached_end) / len(self.normal_sent_time)

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["AwaySent"]               = lambda x: x.number_sent("Away")
        d["BeaconSent"]             = lambda x: x.number_sent("Beacon")
        d["PathsReachedEnd"]        = lambda x: x.paths_reached_end()

        return d

    @staticmethod
    def printHeader(stream=sys.stdout):
        print("#" + "|".join(Metrics.items().keys()), file=stream)

    def print_results(self, stream=sys.stdout):
        results = [str(f(self)) for f in Metrics.items().values()]
        
        print("|".join(results), file=stream)
