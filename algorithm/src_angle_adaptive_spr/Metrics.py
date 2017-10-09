from __future__ import print_function, division

from collections import defaultdict

from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):

    def __init__(self, *args, **kwargs):
        super(Metrics, self).__init__(*args, **kwargs)

        self.register('Metric-Angle', self.process_ANGLE)

        self.angles = defaultdict(dict)
        self.angles_count = defaultdict(dict)

    def process_ANGLE(self, d_or_e, node_id, time, detail):
        (source1, source2, angle) = detail.split(",")

        ord_node_id, top_node_id = self._process_node_id(node_id)
        ord_source1, top_source1 = self._process_node_id(source1)
        ord_source2, top_source2 = self._process_node_id(source2)
        angle = float(angle)

        key = tuple(sorted((top_source1, top_source2)))

        kd = self.angles[key]

        if node_id not in kd:
            self.angles_count[key][top_node_id] = 1
            kd[top_node_id] = angle
        else:
            self.angles_count[key][top_node_id] += 1
            kd[top_node_id] = kd[top_node_id] + (angle - kd[top_node_id]) / self.angles_count[key][top_node_id]

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
