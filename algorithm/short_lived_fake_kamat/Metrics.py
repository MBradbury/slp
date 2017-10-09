from __future__ import print_function, division

from simulator.MetricsCommon import MetricsCommon, FakeMetricsCommon

class Metrics(FakeMetricsCommon):

    def __init__(self, *args, **kwargs):
        super(Metrics, self).__init__(*args, **kwargs)

    @staticmethod
    def items():
        d = MetricsCommon.items()

        d.update(FakeMetricsCommon.items({"TFS": "TempFakeNode"}))

        return d
