
from simulator.Simulator import OutputCatcher
from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):
    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

        self.register('Metric-COMMUNICATE', self.process_COMMUNICATE)
        
        # Normal nodes becoming the source, or source nodes becoming normal
        self.register('Metric-SOURCE_CHANGE', self.process_SOURCE_CHANGE)

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
