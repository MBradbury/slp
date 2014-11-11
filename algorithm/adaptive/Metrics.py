from __future__ import print_function

import sys, re

from numpy import mean
from scipy.spatial.distance import euclidean

from collections import Counter

from simulator.Simulator import OutputCatcher

class Metrics:

    WHOLE_RE  = re.compile(r'DEBUG \((\d+)\): (.*)')
    FAKE_RE   = re.compile(r'The node has become a ([a-zA-Z]+)')

    def __init__(self, sim, configuration):
        self.sim = sim

        self.sourceID = configuration.sourceId
        self.sinkID = configuration.sinkId

        self.BCAST = OutputCatcher(self.process_BCAST)
        self.sim.tossim.addChannel('Metric-BCAST', self.BCAST.write)
        self.sim.addOutputProcessor(self.BCAST)

        self.RCV = OutputCatcher(self.process_RCV)
        self.sim.tossim.addChannel('Metric-RCV', self.RCV.write)
        self.sim.addOutputProcessor(self.RCV)

        self.FAKE_NOTIFICATION = OutputCatcher(self.process_FAKE_NOTIFICATION)
        self.sim.tossim.addChannel('Fake-Notification', self.FAKE_NOTIFICATION.write)
        self.sim.addOutputProcessor(self.FAKE_NOTIFICATION)

        self.heatMap = {}

        self.normalSentTime = {}
        self.normalLatency = {}

        self.sent = {}
        self.received = {}

        self.tfsCreated = 0
        self.pfsCreated = 0
        self.fakeToNormal = 0

    def process_BCAST(self, line):
        (kind, time, nodeID, status, seqNo) = line.split(',')

        if status == "success":
            time = float(time) / self.sim.tossim.ticksPerSecond()
            nodeID = int(nodeID)
            seqNo = int(seqNo)

            if nodeID == self.sourceID and kind == "Normal":
                self.normalSentTime[seqNo] = time

            if kind not in self.sent:
                self.sent[kind] = Counter()

            self.sent[kind][nodeID] += 1


    def process_RCV(self, line):
        (kind, time, nodeID, sourceID, seqNo) = line.split(',')

        time = float(time) / self.sim.tossim.ticksPerSecond()
        nodeID = int(nodeID)
        sourceID = int (sourceID)
        seqNo = int(seqNo)

        if nodeID == self.sinkID and kind == "Normal":
            self.normalLatency[seqNo] = time - self.normalSentTime[seqNo]

        if kind not in self.received:
            self.received[kind] = Counter()

        self.received[kind][nodeID] += 1

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

    def averageNormalLatency(self):
        return mean(self.normalLatency.values())

    def receivedRatio(self):
        return float(len(self.normalLatency)) / len(self.normalSentTime)

    def attackerDistance(self):
        sourceLocation = self.sim.nodes[self.sourceID].location

        return {
            i: euclidean(sourceLocation, self.sim.nodes[attacker.position].location)
            for i, attacker
            in enumerate(self.sim.attackers)
        }

    @staticmethod
    def printHeader(stream=sys.stdout):
        print("#Seed,Sent,Received,Collisions,Captured,ReceiveRatio,TimeTaken,AttackerDistance,AttackerMoves,NormalLatency,NormalSent,FakeSent,ChooseSent,AwaySent,TFS,PFS,FakeToNormal,SentHeatMap,ReceivedHeatMap".replace(",", "|"), file=stream)

    def printResults(self, stream=sys.stdout):
        seed = self.sim.seed

        def numSent(name):
            return 0 if name not in self.sent else sum(self.sent[name].values())

        normalSent = numSent("Normal")
        fakeSent = numSent("Fake")
        chooseSent = numSent("Choose")
        awaySent = numSent("Away")
        sent = sum(sum(sent.values()) for sent in self.sent.values())
        received = sum(sum(received.values()) for received in self.received.values())
        collisions = None
        captured = self.sim.anyAttackerFoundSource()
        receivedRatio = self.receivedRatio()
        time = self.sim.simTime()
        attackerDistance = self.attackerDistance()
        attackerMoves = {i: attacker.moves for i, attacker in enumerate(self.sim.attackers)}
        normalLatency = self.averageNormalLatency()

        sentHeatMap = dict(sum(self.sent.values(), Counter()))
        receivedHeatMap = dict(sum(self.received.values(), Counter()))

        print("|".join(["{}"] * 19).format(
            seed, sent, received, collisions, captured,
            receivedRatio, time, attackerDistance, attackerMoves,
            normalLatency, normalSent, fakeSent, chooseSent, awaySent,
            self.tfsCreated, self.pfsCreated, self.fakeToNormal,
            sentHeatMap, receivedHeatMap), file=stream)
