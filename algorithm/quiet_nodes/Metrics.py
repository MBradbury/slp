from __future__ import print_function, division

import numpy as np

from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):
    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["AwaySent"]               = lambda x: x.number_sent("Away")
        d["BeaconSent"]             = lambda x: x.number_sent("Beacon")

        return d
