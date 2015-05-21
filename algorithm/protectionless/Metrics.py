from __future__ import print_function

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

    def process_BCAST(self, line):
        kind = line.split(',')[0]

        if kind != "Normal":
            raise RuntimeError("Unknown message type of {}".format(kind))

        super(Metrics, self).process_BCAST(line)

    def process_RCV(self, line):
        kind = line.split(',')[0]

        if kind != "Normal":
            raise RuntimeError("Unknown message type of {}".format(kind))

        super(Metrics, self).process_RCV(line)

    @staticmethod
    def items():
        d = MetricsCommon.items()
        return d

    @staticmethod
    def print_header(stream=sys.stdout):
        print("#" + "|".join(Metrics.items().keys()), file=stream)

    def print_results(self, stream=sys.stdout):
        results = [str(f(self)) for f in Metrics.items().values()]

        print("|".join(results), file=stream)
