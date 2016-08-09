
from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):

    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["FakeSent"]               = lambda x: x.number_sent("Fake")
        d["ChooseSent"]             = lambda x: x.number_sent("Choose")
        d["AwaySent"]               = lambda x: x.number_sent("Away")
        d["TFS"]                    = lambda x: x.times_node_changed_to("TempFakeNode")
        d["PFS"]                    = lambda x: x.times_node_changed_to("PermFakeNode")
        d["FakeToNormal"]           = lambda x: x.times_node_changed_to("NormalNode", from_types=("TempFakeNode", "PermFakeNode"))

        return d
