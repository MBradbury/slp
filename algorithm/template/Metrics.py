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

        self.tfsCreated = 0
        self.pfsCreated = 0
        self.fakeToNormal = 0

    def process_FAKE_NOTIFICATION(self, line):
        match = self.WHOLE_RE.match(line)
        if match is None:
            return None

        id = int(match.group(1))
        detail = match.group(2)

        match = self.FAKE_RE.match(detail)
        if match is not None:
            kind = match.group(1)
            
            if kind == "TFS":
                self.tfsCreated += 1
            elif kind == "PFS":
                self.pfsCreated += 1
            elif kind == "Normal":
                self.fakeToNormal += 1
            elif kind == "Sink":
                pass
            elif kind == "Source":
                pass
            else:
                raise RuntimeError("Unknown kind {}".format(kind))

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["FakeSent"]               = lambda x: x.numberSent("Fake")
        d["ChooseSent"]             = lambda x: x.numberSent("Choose")
        d["AwaySent"]               = lambda x: x.numberSent("Away")
        d["TFS"]                    = lambda x: x.tfsCreated
        d["PFS"]                    = lambda x: x.pfsCreated
        d["FakeToNormal"]           = lambda x: x.fakeToNormal

        return d

    @staticmethod
    def printHeader(stream=sys.stdout):
        print("#" + "|".join(Metrics.items().keys()), file=stream)

    def print_results(self, stream=sys.stdout):
        results = [str(f(self)) for f in Metrics.items().values()]
        
        print("|".join(results), file=stream)
