from __future__ import print_function

import re

from simulator.Simulation import OutputCatcher
from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):

    WHOLE_RE  = re.compile(r'DEBUG \((\d+)\): (.*)')
    FAKE_RE   = re.compile(r'The node has become a ([a-zA-Z]+) was ([a-zA-Z]+)')

    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

        self.register('Fake-Notification', self.process_FAKE_NOTIFICATION)

        self.tfs_created = 0
        self.fake_to_normal = 0

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

            if new_kind == "TempFakeNode":
                self.tfs_created += 1
            elif new_kind == "NormalNode":
                self.fake_to_normal += 1
            else:
                raise RuntimeError("Unknown kind {}".format(new_kind))

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["FakeSent"]               = lambda x: x.number_sent("Fake")
        d["TFS"]                    = lambda x: x.tfs_created
        d["FakeToNormal"]           = lambda x: x.fake_to_normal

        return d
