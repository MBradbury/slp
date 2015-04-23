from __future__ import print_function

import sys, re

from simulator.Simulator import OutputCatcher
from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):

    WHOLE_RE  = re.compile(r'DEBUG \((\d+)\): (.*)')
    FAKE_RE   = re.compile(r'The node has become a ([a-zA-Z]+)')

    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

        self.BCAST = OutputCatcher(self.process_BCAST)
        self.sim.tossim.addChannel('Metric-BCAST', self.BCAST.write)
        self.sim.add_output_processor(self.BCAST)

        self.RCV = OutputCatcher(self.process_RCV)
        self.sim.tossim.addChannel('Metric-RCV', self.RCV.write)
        self.sim.add_output_processor(self.RCV)

        self.FAKE_NOTIFICATION = OutputCatcher(self.process_FAKE_NOTIFICATION)
        self.sim.tossim.addChannel('Fake-Notification', self.FAKE_NOTIFICATION.write)
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

    @staticmethod
    def printHeader(stream=sys.stdout):
        print("#" + "|".join(Metrics.items().keys()), file=stream)

    def print_results(self, stream=sys.stdout):
        results = [str(f(self)) for f in Metrics.items().values()]
        
        print("|".join(results), file=stream)
