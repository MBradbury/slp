from __future__ import division

from simulator.MetricsCommon import MetricsCommon

from numpy import mean

class Metrics(MetricsCommon):
    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

    @staticmethod
    def items():
        d = MetricsCommon.items()
        return d
