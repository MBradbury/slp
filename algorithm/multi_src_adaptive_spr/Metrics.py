from __future__ import print_function, division

import re
from collections import defaultdict

from simulator.Simulation import OutputCatcher
from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):

    WHOLE_RE  = re.compile(r'DEBUG \((\d+)\): (.*)')
    FAKE_RE   = re.compile(r'The node has become a ([a-zA-Z]+) was ([a-zA-Z]+)')

    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

        self.register('Fake-Notification', self.process_FAKE_NOTIFICATION)
        self.register('Metric-Angle', self.process_ANGLE)

        self.tfs_created = 0
        self.pfs_created = 0
        self.tailfs_created = 0
        self.fake_to_normal = 0
        self.fake_to_fake = 0

        self.angles = defaultdict(dict)
        self.angles_count = defaultdict(dict)

    def process_FAKE_NOTIFICATION(self, line):
        match = self.WHOLE_RE.match(line)
        if match is None:
            return None

        node_id = int(match.group(1))
        detail = match.group(2)

        match = self.FAKE_RE.match(detail)
        if match is not None:
            new_kind = match.group(1)
            old_kind = match.group(2)

            if "FakeNode" in new_kind and "FakeNode" in old_kind:
                self.fake_to_fake += 1
            
            if new_kind == "TempFakeNode":
                self.tfs_created += 1
            elif new_kind == "PermFakeNode":
                self.pfs_created += 1
            elif new_kind == "TailFakeNode":
                self.tailfs_created += 1
            elif new_kind == "NormalNode":
                self.fake_to_normal += 1
            else:
                raise RuntimeError("Unknown kind {}".format(new_kind))

    def process_ANGLE(self, line):
        (node_id, source1, source2, angle) = line.split(",")

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
        d["TFS"]                    = lambda x: x.tfs_created
        d["PFS"]                    = lambda x: x.pfs_created
        d["TailFS"]                 = lambda x: x.tailfs_created
        d["FakeToNormal"]           = lambda x: x.fake_to_normal
        d["FakeToFake"]             = lambda x: x.fake_to_fake

        d["Angles"]                 = lambda x: dict(x.angles)
        d["AnglesCount"]            = lambda x: dict(x.angles_count)

        return d
