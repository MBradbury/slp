from __future__ import print_function

from collections import Counter
import sys

from numpy import mean
from scipy.spatial.distance import euclidean

from simulator.Simulator import OutputCatcher

class Metrics:
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

        self.heatMap = {}

        self.normalSentTime = {}
        self.normalLatency = {}
        self.normalHopCount = []

        self.normalSent = Counter()
        self.normalReceived = Counter()

    def process_BCAST(self, line):
        (kind, time, nodeID, status, seqNo) = line.split(',')

        if kind != "Normal":
            raise Exception("Unknown message type of {}".format(kind))

        if status == "success":
            time = float(time) / self.sim.tossim.ticksPerSecond()
            nodeID = int(nodeID)
            seqNo = int(seqNo)

            if nodeID == self.sourceID:
                self.normalSentTime[seqNo] = time

            self.normalSent[nodeID] += 1


    def process_RCV(self, line):
        (kind, time, nodeID, sourceID, seqNo, hopCount) = line.split(',')

        if kind != "Normal":
            raise Exception("Unknown message type of {}".format(kind))

        time = float(time) / self.sim.tossim.ticksPerSecond()
        nodeID = int(nodeID)
        sourceID = int(sourceID)
        seqNo = int(seqNo)
        hopCount = int(hopCount)

        if nodeID == self.sinkID:
            self.normalLatency[seqNo] = time - self.normalSentTime[seqNo]
            self.normalHopCount.append(hopCount)

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

    def averageSinkSourceHops(self):
        return mean(self.normalHopCount)

    @staticmethod
    def printHeader(stream=sys.stdout):
        print("#Seed,Sent,Received,Collisions,Captured,ReceiveRatio,TimeTaken,AttackerDistance,AttackerMoves,NormalLatency,NormalSinkSourceHops,NormalSent,SentHeatMap,ReceivedHeatMap".replace(",", "|"), file=stream)

    def printResults(self, stream=sys.stdout):
        seed = self.sim.seed

        normalSent = sum(self.normalSent.values())
        sent = normalSent
        received = sum(self.normalReceived.values())
        collisions = None
        captured = self.sim.anyAttackerFoundSource()
        receivedRatio = self.receivedRatio()
        time = float(self.sim.tossim.time()) / self.sim.tossim.ticksPerSecond()
        attackerDistance = self.attackerDistance()
        attackerMoves = {i: attacker.moves for i, attacker in enumerate(self.sim.attackers)}
        normalLatency = self.averageNormalLatency()
        averageSinkSourceHops = self.averageSinkSourceHops()

        sentHeatMap = dict(self.normalSent)
        receivedHeatMap = dict(self.normalReceived)

        print("|".join(["{}"] * 14).format(
            seed, sent, received, collisions, captured,
            receivedRatio, time, attackerDistance, attackerMoves, normalLatency,
            averageSinkSourceHops, normalSent, sentHeatMap, receivedHeatMap),
            file=stream)
