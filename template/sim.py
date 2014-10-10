#!/usr/bin/python
# TODO: Eventually replace this using C++
# Python bindings will be slow

from __future__ import print_function, absolute_import

import template.TOSSIM as TOSSIM

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

        self.BCAST = OutputCatcher(self.process_BCAST)
        self.sim.tossim.addChannel('Metric-BCAST', self.BCAST.write)
        self.sim.addOutputProcessor(self.BCAST)

        self.RCV = OutputCatcher(self.process_RCV)
        self.sim.tossim.addChannel('Metric-RCV', self.RCV.write)
        self.sim.addOutputProcessor(self.RCV)

        self.heatMap = {}

        self.normalSentTime = {}
        self.normalLatency = {}

        self.sent = {}
        self.received = {}

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
        attackerHopDistance = None
        attackerDistance = self.attackerDistance()
        attackerMoves = {i: attacker.moves for i, attacker in enumerate(self.sim.attackers)}
        normalLatency = self.averageNormalLatency()

        sentHeatMap = dict(sum(self.sent.values(), Counter()))
        receivedHeatMap = dict(sum(self.received.values(), Counter()))

        print(",".join(["{}"] * 17).format(
            seed, sent, received, collisions, captured,
            receivedRatio, time, attackerHopDistance, attackerDistance, attackerMoves,
            normalLatency, normalSent, fakeSent, chooseSent, awaySent,
            sentHeatMap, receivedHeatMap))


class Simulation(TosVis):
    def __init__(self, seed, configuration, range, safetyPeriod):

        self.seed = int(seed)
        self.safetyPeriod = float(safetyPeriod)

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
        return not self.anyAttackerFoundSource() and self.simTime() < self.safetyPeriod

    def anyAttackerFoundSource(self):
        return any(attacker.foundSource() for attacker in self.attackers)

    def setSeed(self):
        self.tossim.randomSeed(self.seed)

