
from simulator.Simulator import OutputCatcher
from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):
    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

        self.register('Metric-COMMUNICATE', self.process_COMMUNICATE)

        # Normal nodes becoming the source, or source nodes becoming normal
        self.register('Metric-SOURCE_CHANGE', self.process_SOURCE_CHANGE)

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["DummyNormalSent"]               = lambda x: x.number_sent("DummyNormal")

        return d
