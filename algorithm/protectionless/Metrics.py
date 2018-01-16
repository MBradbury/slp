
from simulator.MetricsCommon import MetricsCommon, DutyCycleMetricsCommon

class Metrics(DutyCycleMetricsCommon):
    def __init__(self, *args, **kwargs):
        super(Metrics, self).__init__(*args, **kwargs)

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d.update(DutyCycleMetricsCommon.items())
        return d
