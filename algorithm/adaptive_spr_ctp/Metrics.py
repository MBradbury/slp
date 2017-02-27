from __future__ import print_function, division

from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):

    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

    def times_fake_node_changed_to_fake(self):
        total_count = 0

        for ((old_type, new_type), count) in self.node_transitions.items():

            if "FakeNode" in old_type and "FakeNode" in new_type:
                total_count += count

        return total_count

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["FakeSent"]               = lambda x: x.number_sent("Fake")
        d["ChooseSent"]             = lambda x: x.number_sent("Choose")
        d["AwaySent"]               = lambda x: x.number_sent("Away")
        d["BeaconSent"]             = lambda x: x.number_sent("Beacon")
        d["InformSent"]             = lambda x: x.number_sent("Inform")
        d["CTPBeaconSent"]          = lambda x: x.number_sent("CTPBeacon")

        d["TFS"]                    = lambda x: x.times_node_changed_to("TempFakeNode")
        d["PFS"]                    = lambda x: x.times_node_changed_to("PermFakeNode")
        d["TailFS"]                 = lambda x: x.times_node_changed_to("TailFakeNode")
        d["FakeToNormal"]           = lambda x: x.times_node_changed_to("NormalNode", from_types=("TempFakeNode", "PermFakeNode", "TailFakeNode"))
        d["FakeToFake"]             = lambda x: x.times_fake_node_changed_to_fake()
        d["FakeNodesAtEnd"]         = lambda x: x.times_node_changed_to(("TempFakeNode", "PermFakeNode", "TailFakeNode"), from_types="NormalNode") - \
                                                x.times_node_changed_to("NormalNode", from_types=("TempFakeNode", "PermFakeNode", "TailFakeNode"))

        return d
