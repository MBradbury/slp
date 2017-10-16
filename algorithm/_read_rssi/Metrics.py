from __future__ import print_function, division

from simulator.MetricsCommon import MetricsCommon, RssiMetricsCommon

class Metrics(RssiMetricsCommon):
    def __init__(self, *args, **kwargs):
        super(Metrics, self).__init__(*args, **kwargs)

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d.update(RssiMetricsCommon.items())
        return d
