
from collections import Counter, OrderedDict

from numpy import mean
from scipy.spatial.distance import euclidean

class MetricsCommon(object):
    def __init__(self, sim, configuration):
        self.sim = sim
        self.configuration = configuration

        self.sourceID = configuration.sourceId
        self.sinkID = configuration.sinkId

        self.sent = {}
        self.received = {}

        self.normalSentTime = {}
        self.normalLatency = {}
        self.normalHopCount = []

        self.wallTime = 0
        self.eventCount = 0

    def process_BCAST(self, line):
        (kind, time, nodeID, status, seqNo) = line.split(',')

        if status == "success":
            time = float(time) / self.sim.tossim.ticksPerSecond()
            nodeID = int(nodeID)
            seqNo = int(seqNo)

            if kind not in self.sent:
                self.sent[kind] = Counter()

            self.sent[kind][nodeID] += 1

            if nodeID == self.sourceID and kind == "Normal":
                self.normalSentTime[seqNo] = time

    def process_RCV(self, line):
        (kind, time, nodeID, sourceID, seqNo, hopCount) = line.split(',')

        time = float(time) / self.sim.tossim.ticksPerSecond()
        nodeID = int(nodeID)
        sourceID = int (sourceID)
        seqNo = int(seqNo)
        hopCount = int(hopCount)

        if kind not in self.received:
            self.received[kind] = Counter()

        self.received[kind][nodeID] += 1

        if nodeID == self.sinkID and kind == "Normal":
            self.normalLatency[seqNo] = time - self.normalSentTime[seqNo]
            self.normalHopCount.append(hopCount)

    def seed(self):
        return self.sim.seed

    def simTime(self):
        return self.sim.simTime()

    def numberSent(self, name):
        return 0 if name not in self.sent else sum(self.sent[name].values())

    def numberReceived(self, name):
        return 0 if name not in self.received else sum(self.received[name].values())

    def totalSent(self):
        return sum(sum(sent.values()) for sent in self.sent.values())

    def totalReceived(self):
        return sum(sum(received.values()) for received in self.received.values())

    def sentHeatMap(self):
        return dict(sum(self.sent.values(), Counter()))

    def receivedHeatMap(self):
        return dict(sum(self.received.values(), Counter()))

    def averageNormalLatency(self):
        return mean(self.normalLatency.values())

    def receivedRatio(self):
        return float(len(self.normalLatency)) / len(self.normalSentTime)

    def averageSinkSourceHops(self):
        return mean(self.normalHopCount)

    def captured(self):
        return self.sim.anyAttackerFoundSource()

    def attackerDistance(self):
        sourceLocation = self.sim.nodes[self.sourceID].location

        return {
            i: euclidean(sourceLocation, self.sim.nodes[attacker.position].location)
            for i, attacker
            in enumerate(self.sim.attackers)
        }

    def attackerMoves(self):
        return {
            i: attacker.moves
            for i, attacker
            in enumerate(self.sim.attackers)
        }

    @staticmethod
    def items():
        d = OrderedDict()
        d["Seed"]                   = lambda x: x.seed()
        d["Sent"]                   = lambda x: x.totalSent()
        d["Received"]               = lambda x: x.totalReceived()
        d["Collisions"]             = lambda x: None
        d["Captured"]               = lambda x: x.captured()
        d["ReceiveRatio"]           = lambda x: x.receivedRatio()
        d["TimeTaken"]              = lambda x: x.simTime()
        d["WallTime"]               = lambda x: x.wallTime
        d["EventCount"]             = lambda x: x.eventCount
        d["AttackerDistance"]       = lambda x: x.attackerDistance()
        d["AttackerMoves"]          = lambda x: x.attackerMoves()
        d["NormalLatency"]          = lambda x: x.averageNormalLatency()
        d["NormalSinkSourceHops"]   = lambda x: x.averageSinkSourceHops()
        d["NormalSent"]             = lambda x: x.numberSent("Normal")
        d["SentHeatMap"]            = lambda x: x.sentHeatMap()
        d["ReceivedHeatMap"]        = lambda x: x.receivedHeatMap()

        return d
