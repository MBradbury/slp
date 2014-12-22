from __future__ import print_function

import sys, re

from collections import Counter

from simulator.Simulator import OutputCatcher
from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):

    WHOLE_RE  = re.compile(r'DEBUG \((\d+)\): (.*)')
    FAKE_RE   = re.compile(r'The node has become a ([a-zA-Z]+)')

    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

        self.BCAST = OutputCatcher(self.process_BCAST)
        self.sim.tossim.addChannel('Metric-BCAST', self.BCAST.write)
        self.sim.addOutputProcessor(self.BCAST)

        self.RCV = OutputCatcher(self.process_RCV)
        self.sim.tossim.addChannel('Metric-RCV', self.RCV.write)
        self.sim.addOutputProcessor(self.RCV)

        self.FAKE_NOTIFICATION = OutputCatcher(self.process_FAKE_NOTIFICATION)
        self.sim.tossim.addChannel('Fake-Notification', self.FAKE_NOTIFICATION.write)
        self.sim.addOutputProcessor(self.FAKE_NOTIFICATION)

        self.SOURCE_CHANGE = OutputCatcher(self.process_SOURCE_CHANGE)
        self.sim.tossim.addChannel('Metric-SOURCE_CHANGE', self.SOURCE_CHANGE.write)
        self.sim.addOutputProcessor(self.SOURCE_CHANGE)

        self.tfsCreated = 0
        self.pfsCreated = 0
        self.fakeToNormal = 0

    def process_RCV(self, line):
        (kind, time, nodeID, neighbourSourceID, ultimateSourceID, seqNo, hopCount) = line.split(',')

        time = float(time) / self.sim.tossim.ticksPerSecond()
        nodeID = int(nodeID)
        neighbourSourceID = int(neighbourSourceID)
        ultimateSourceID = int(ultimateSourceID)
        seqNo = int(seqNo)
        hopCount = int(hopCount)

        if kind not in self.received:
            self.received[kind] = Counter()

        self.received[kind][nodeID] += 1

        if nodeID == self.sinkID and kind == "Normal":
            self.normalLatency[seqNo] = time - self.normalSentTime[seqNo]
            self.normalHopCount.append(hopCount)

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
            else:
                raise RuntimeError("Unknown kind {}".format(kind))

    def process_SOURCE_CHANGE(self, line):
        (time, nodeID, previousSourceID, currentSourceID) = line.split(',')

        time = float(time) / self.sim.tossim.ticksPerSecond()
        nodeID = int(nodeID)
        previousSourceID = int(previousSourceID)
        currentSourceID = int(currentSourceID)

        # TODO: proper metrics for this information
        # Ideas:
        # - Delay between a source change and a node detecting it
        #
        #
        print("On {} source changes from {} to {}".format(nodeID, previousSourceID, currentSourceID))


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

    def printResults(self, stream=sys.stdout):
        results = [str(f(self)) for f in Metrics.items().values()]
        
        print("|".join(results), file=stream)
