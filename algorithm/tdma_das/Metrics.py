
from simulator.Simulator import OutputCatcher
from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):
    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["DummyNormalSent"]               = lambda x: x.number_sent("DummyNormal")
        d["BeaconSent"]                    = lambda x: x.number_sent("Beacon")

        return d
