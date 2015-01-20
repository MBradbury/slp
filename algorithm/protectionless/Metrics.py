from __future__ import print_function

import sys

from simulator.Simulator import OutputCatcher
from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):
    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

        self.BCAST = OutputCatcher(self.process_BCAST)
        self.sim.tossim.addChannel('Metric-BCAST', self.BCAST.write)
        self.sim.add_output_processor(self.BCAST)

        self.RCV = OutputCatcher(self.process_RCV)
        self.sim.tossim.addChannel('Metric-RCV', self.RCV.write)
        self.sim.add_output_processor(self.RCV)

    def process_BCAST(self, line):
        (kind, time, nodeID, status, seqNo) = line.split(',')

        if kind != "Normal":
            raise RuntimeError("Unknown message type of {}".format(kind))

        super(Metrics, self).process_BCAST(line)


    def process_RCV(self, line):
        (kind, time, nodeID, sourceID, seqNo, hopCount) = line.split(',')

        if kind != "Normal":
            raise RuntimeError("Unknown message type of {}".format(kind))

        super(Metrics, self).process_RCV(line)

    @staticmethod
    def items():
        d = MetricsCommon.items()
        return d

    @staticmethod
    def printHeader(stream=sys.stdout):
        print("#" + "|".join(Metrics.items().keys()), file=stream)

    def print_results(self, stream=sys.stdout):
        results = [str(f(self)) for f in Metrics.items().values()]

        print("|".join(results), file=stream)
