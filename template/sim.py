#!/usr/bin/python
# TODO: Eventually replace this using C++
# Python bindings will be slow

from __future__ import print_function, absolute_import

import protectionless.TOSSIM as TOSSIM

import os
import struct
import sys
import random

from simulator.TosVis import *
from simulator.Simulator import *
from simulator.Attacker import Attacker

from numpy import mean
from scipy.spatial.distance import euclidean

from collections import Counter

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

    def printResults(self):
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
            normalLatency, normalSent, sentHeatMap, receivedHeatMap))


class Simulation(Simulator):
    def __init__(self, seed, configuration, range):

        self.seed = int(seed)

        super(Simulation, self).__init__(
            TOSSIM,
            node_locations=configuration.topology.nodes,
            range=range
            )

#       self.tossim.addChannel("Metric-BCAST-Normal", sys.stdout)
#       self.tossim.addChannel("Metric-RCV-Normal", sys.stdout)
#       self.tossim.addChannel("Boot", sys.stdout)
#       self.tossim.addChannel("SourceBroadcasterC", sys.stdout)
#       self.tossim.addChannel("Attacker-RCV", sys.stdout)

        self.attackers = [Attacker(self, configuration.sourceId, configuration.sinkId)]

        self.metrics = Metrics(self, configuration.sourceId, configuration.sinkId)

    def continuePredicate(self):
        return not self.anyAttackerFoundSource()

    def anyAttackerFoundSource(self):
        return any(attacker.foundSource() for attacker in self.attackers)

    def setSeed(self):
        self.tossim.randomSeed(self.seed)

