
from simulator.MetricsCommon import DutyCycleMetricsCommon

from algorithm.phantom.Metrics import Metrics as MetricsCommon

class Metrics(MetricsCommon, DutyCycleMetricsCommon):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d.update(DutyCycleMetricsCommon.items())

        return d
