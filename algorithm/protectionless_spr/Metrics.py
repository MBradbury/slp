from __future__ import print_function, division

from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):
    def __init__(self, *args, **kwargs):
        super(Metrics, self).__init__(*args, **kwargs)

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["AwaySent"]               = lambda x: x.number_sent("Away")
        
        return d
