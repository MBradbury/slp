
from simulator.Simulation import OutputCatcher
from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):
    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["DissemSent"]               = lambda x: x.number_sent("Dissem")

        return d
