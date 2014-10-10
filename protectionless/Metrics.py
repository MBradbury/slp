from __future__ import print_function

from collections import Counter
import sys

from numpy import mean
from scipy.spatial.distance import euclidean

from simulator.Simulator import OutputCatcher

class Metrics:
    def __init__(self, sim, sourceID, sinkID):
        self.sim = sim

        self.sourceID = sourceID
        self.sinkID = sinkID

        self.BCAST_Normal = OutputCatcher(self.process_BCAST_Normal)
        self.sim.tossim.addChannel('Metric-BCAST-Normal', self.BCAST_Normal.write)
        self.sim.addOutputProcessor(self.BCAST_Normal)

        self.RCV_Normal = OutputCatcher(self.process_RCV_Normal)
        self.sim.tossim.addChannel('Metric-RCV-Normal', self.RCV_Normal.write)
        self.sim.addOutputProcessor(self.RCV_Normal)

        self.heatMap = {}

        self.normalSentTime = {}
        self.normalLatency = {}

        self.normalSent = Counter()
        self.normalReceived = Counter()

    def process_BCAST_Normal(self, line):
        (time, nodeID, status, seqNo) = line.split(',')

        if status == "success":
            time = float(time) / self.sim.tossim.ticksPerSecond()
            nodeID = int(nodeID)
            seqNo = int(seqNo)

            if nodeID == self.sourceID:
                self.normalSentTime[seqNo] = time

            self.normalSent[nodeID] += 1


    def process_RCV_Normal(self, line):
        (time, nodeID, sourceID, seqNo) = line.split(',')

        time = float(time) / self.sim.tossim.ticksPerSecond()
        nodeID = int(nodeID)
        sourceID = int (sourceID)
        seqNo = int(seqNo)

        if nodeID == self.sinkID:
            self.normalLatency[seqNo] = time - self.normalSentTime[seqNo]

        self.normalReceived[nodeID] += 1

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

    def printResults(self, stream=sys.stdout):
        seed = self.sim.seed

        normalSent = sum(self.normalSent.values())
        sent = normalSent
        received = sum(self.normalReceived.values())
        collisions = None
        captured = self.sim.anyAttackerFoundSource()
        receivedRatio = self.receivedRatio()
        time = float(self.sim.tossim.time()) / self.sim.tossim.ticksPerSecond()
        attackerHopDistance = None
        attackerDistance = self.attackerDistance()
        attackerMoves = {i: attacker.moves for i, attacker in enumerate(self.sim.attackers)}
        normalLatency = self.averageNormalLatency()

        # TODO: when more message types are involved, sum those Counters together
        sentHeatMap = dict(self.normalSent)
        receivedHeatMap = dict(self.normalReceived)

        print(",".join(["{}"] * 14).format(
            seed, sent, received, collisions, captured,
            receivedRatio, time, attackerHopDistance, attackerDistance, attackerMoves,
            normalLatency, normalSent, sentHeatMap, receivedHeatMap),
            file=stream)
