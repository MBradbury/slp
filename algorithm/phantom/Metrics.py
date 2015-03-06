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

        # Should be CpmModelC, but that has a very large performance impact
        # So the source was modified to add PacketLoss.
        #self.COLLISIONS = OutputCatcher(self.process_COLLISIONS)
        #self.sim.tossim.addChannel('PacketLoss', self.COLLISIONS.write)
        #self.sim.add_output_processor(self.COLLISIONS)    

        self.RCV = OutputCatcher(self.process_RCV)
        self.sim.tossim.addChannel('Metric-RCV', self.RCV.write)
        self.sim.add_output_processor(self.RCV)

        # Normal nodes becoming the source, or source nodes becoming normal
        self.SOURCE_CHANGE = OutputCatcher(self.process_SOURCE_CHANGE)
        self.sim.tossim.addChannel('Metric-SOURCE_CHANGE', self.SOURCE_CHANGE.write)
        self.sim.add_output_processor(self.SOURCE_CHANGE)

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
