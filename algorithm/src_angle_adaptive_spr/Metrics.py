from __future__ import print_function, division

from collections import defaultdict

from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):

    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

        self.register('Metric-Angle', self.process_ANGLE)

        self.angles = defaultdict(dict)
        self.angles_count = defaultdict(dict)

    def process_ANGLE(self, d_or_e, node_id, time, detail):
        (source1, source2, angle) = detail.split(",")

        node_id = int(node_id)
        source1 = int(source1)
        source2 = int(source2)
        angle = float(angle)

        key = tuple(sorted((source1, source2)))

        kd = self.angles[key]

        if node_id not in kd:
            self.angles_count[key][node_id] = 1
            kd[node_id] = angle
        else:
            self.angles_count[key][node_id] += 1
            kd[node_id] = kd[node_id] + (angle - kd[node_id]) / self.angles_count[key][node_id]

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["FakeSent"]               = lambda x: x.number_sent("Fake")
        d["ChooseSent"]             = lambda x: x.number_sent("Choose")
        d["AwaySent"]               = lambda x: x.number_sent("Away")
        d["BeaconSent"]             = lambda x: x.number_sent("Beacon")
        d["DummyNormalSent"]        = lambda x: x.number_sent("DummyNormal")
        d["TFS"]                    = lambda x: x.times_node_changed_to("TempFakeNode")
        d["PFS"]                    = lambda x: x.times_node_changed_to("PermFakeNode")
        d["TailFS"]                 = lambda x: x.times_node_changed_to("TailFakeNode")
        d["FakeToNormal"]           = lambda x: x.times_node_changed_to("NormalNode", from_types=("TempFakeNode", "PermFakeNode", "TailFakeNode"))
        d["FakeToFake"]             = lambda x: x.times_fake_node_changed_to_fake()

        d["Angles"]                 = lambda x: dict(x.angles)
        d["AnglesCount"]            = lambda x: dict(x.angles_count)

        return d
