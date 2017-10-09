
from simulator.MetricsCommon import MetricsCommon, TreeMetricsCommon

class Metrics(TreeMetricsCommon):
    def __init__(self, *args, **kwargs):
        super(Metrics, self).__init__(*args, **kwargs)

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["CTPBeaconSent"]               = lambda x: x.number_sent("CTPBeacon")

        d.update(TreeMetricsCommon.items())

        return d
