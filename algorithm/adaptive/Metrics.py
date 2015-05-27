from __future__ import print_function

import re

from simulator.Simulator import OutputCatcher
from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):

    WHOLE_RE  = re.compile(r'DEBUG \((\d+)\): (.*)')
    FAKE_RE   = re.compile(r'The node has become a ([a-zA-Z]+)')

    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

        self.COMMUNICATE = OutputCatcher(self.process_COMMUNICATE)
        self.COMMUNICATE.register(self.sim, 'Metric-COMMUNICATE')
        self.sim.add_output_processor(self.COMMUNICATE)

        self.FAKE_NOTIFICATION = OutputCatcher(self.process_FAKE_NOTIFICATION)
        self.FAKE_NOTIFICATION.register(self.sim, 'Fake-Notification')
        self.sim.add_output_processor(self.FAKE_NOTIFICATION)

        self.tfs_created = 0
        self.pfs_created = 0
        self.fake_to_normal = 0

    def process_FAKE_NOTIFICATION(self, line):
        match = self.WHOLE_RE.match(line)
        if match is None:
            return None

        node_id = int(match.group(1))
        detail = match.group(2)

        match = self.FAKE_RE.match(detail)
        if match is not None:
            kind = match.group(1)
            
            if kind == "TFS":
                self.tfs_created += 1
            elif kind == "PFS":
                self.pfs_created += 1
            elif kind == "Normal":
                self.fake_to_normal += 1
            else:
                raise RuntimeError("Unknown kind {}".format(kind))

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["FakeSent"]               = lambda x: x.number_sent("Fake")
        d["ChooseSent"]             = lambda x: x.number_sent("Choose")
        d["AwaySent"]               = lambda x: x.number_sent("Away")
        d["TFS"]                    = lambda x: x.tfs_created
        d["PFS"]                    = lambda x: x.pfs_created
        d["FakeToNormal"]           = lambda x: x.fake_to_normal
        
        return d
