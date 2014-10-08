#!/usr/bin/python
# TODO: Eventually replace this using C++
# Python bindings will be slow

from __future__ import print_function

from TOSSIM import *

import os
import struct
import sys
import random

from TosVis import *
from Simulator import *

class Attacker:
    def __init__(self, sim, sourceId, sinkId):
        self.sim = sim

        self.out = OutputCatcher(self.process)
        self.sim.tossim.addChannel('Attacker-RCV', self.out.write)

        self.sim.addOutputProcessor(self.out)

        self.seqNos = {}
        self.position = sinkId
        self.sourceId = sourceId

    def foundSource(self):
        return self.position == self.sourceId

    def process(self, line):
        if self.foundSource():
            return

        (time, msgType, nodeID, fromID, seqNo) = line.split(',')

        time = float(time) / self.sim.tossim.ticksPerSecond() # Get time to be in sec
        nodeID = int(nodeID)
        fromID = int(fromID)
        seqNo = int(seqNo)

        if self.position == nodeID and (msgType not in self.seqNos or self.seqNos[msgType] < seqNo):

            self.seqNos[msgType] = seqNo
            self.position = fromID

            print("Attacker moved from {} to {}".format(nodeID, fromID))

            self.draw(time, self.position)

    def draw(self, time, nodeID):
        if not hasattr(self.sim, "scene"):
            return

        (x,y) = self.sim.nodes[nodeID].location

        shapeId = "attacker"

        color = '1,0,0'

        options = 'line=LineStyle(color=(%s)),fill=FillStyle(color=(%s))' % (color,color)

        self.sim.scene.execute(time, 'delshape("%s")' % shapeId)
        self.sim.scene.execute(time, 'circle(%d,%d,5,id="%s",%s)' % (x,y,shapeId,options))



class Simulation(TosVis):
    def __init__(self, seed, nodeLocations, range):

        self.seed = int(seed)

        super(Simulation, self).__init__(
            node_locations=nodeLocations,
            range=range
            )

#       self.tossim.addChannel("Metric-BCAST-Normal", sys.stdout)
#       self.tossim.addChannel("Metric-RCV-Normal", sys.stdout)
#       self.tossim.addChannel("Boot", sys.stdout)
#       self.tossim.addChannel("SourceBroadcasterC", sys.stdout)
#       self.tossim.addChannel("Attacker-RCV", sys.stdout)

        self.attacker = Attacker(self, 0, 60)

    def continuePredicate(self):
        return not self.attacker.foundSource()

    def setSeed(self):
        print(dir(self.tossim))
        self.tossim.randomSeed(self.seed)


class GridSimulation(Simulation):
    def __init__(self, seed, size, range, initialPosition=100):

        range_modifier = 2
        modified_range = range - range_modifier

        nodes = [(x * modified_range + initialPosition, y * modified_range + initialPosition)
            for y in xrange(size)
            for x in xrange(size)]

        super(GridSimulation, self).__init__(
            seed=seed,
            nodeLocations=nodes,
            range=range
            )

networkSize = 11
sourcePeriod = None
configuration = None
networkType = "GRID"

wirelessRange = 45

seed = struct.unpack("<i", os.urandom(4))[0]

sim = GridSimulation(seed, networkSize, wirelessRange)

sim.run()

sent = None
received = None
collisions = None
captured = True
receivedRatio = None
time = float(sim.tossim.time()) / sim.tossim.ticksPerSecond()
attackerHopDistance = {0: 0}
attackerDistance = {0: 0}
attackerMoves = None
normalLatency = None
normalSent = None
heatMap = None

print(",".join(["{}"] * 13).format(
    seed, sent, received, collisions, captured,
    receivedRatio, time, attackerHopDistance, attackerDistance, attackerMoves,
    normalLatency, normalSent, heatMap))

"""
t = Tossim([])
r = t.radio()

t.addChannel("Boot", sys.stdout)
t.addChannel("SourceBroadcasterC", sys.stdout)

pos_to_id = {}

def setup_boot_times(size):
    for i in xrange(1, size*size + 1):
        node = t.getNode(i)

        # All nodes will booth within the first second
        time_to_boot = int(t.ticksPerSecond() * random.random())

        print("Booting {0} at {1}".format(i, time_to_boot))
        node.bootAtTime(time_to_boot)

def create_grid(size):
    def add(coords, neighbour_coords):

        (nrow, ncol) = neighbour_coords

        # Check neighbour is valid
        if nrow >= 0 and nrow < size and ncol >= 0 and ncol < size:

            r.add(pos_to_id[coords], pos_to_id[neighbour_coords], -50.0)

            connected = r.connected(pos_to_id[coords], pos_to_id[neighbour_coords])

            print("Added link: {0} <-> {1} ({2})".format(coords, neighbour_coords, connected))

    node_counter = 1
    for row in range(size):
        for col in range(size):
            coords = (row, col)

            pos_to_id[coords] = node_counter
            node_counter += 1

    for row in range(size):
        for col in range(size):
            coords = (row, col)

            add(coords, (row, col - 1)) # Left
            add(coords, (row, col + 1)) # Right
            add(coords, (row - 1, col)) # Above
            add(coords, (row + 1, col)) # Below

def setup_noise_model(size):
    for i in xrange(1, size*size + 1):

        node = t.getNode(i)

        # Create random noise stream
        for x in xrange(500):
            node.addNoiseTraceReading(int(random.random() * 10) - 80)

        print("Created noise model for {0}".format(i))
        node.createNoiseModel()

def print_matrix(A):
    for i in range(len(A)):
        for j in range(len(A[i])):
            value = A[i][j]
            print('{:5}'.format(value if value else ""), end='')
        print()

def show_network_matrix(size):
    connected_matrix = [[pos_to_id[(x, y)] for y in xrange(size)] for x in xrange(size)]
    print_matrix(connected_matrix)

def show_node_relation_matrix(fn):
    # Create matrix
    matrix = [[0 for x in xrange(size*size+1)] for x in xrange(size*size+1)] 

    # Set up labels
    for x in xrange(size*size+1):
        matrix[0][x] = x
        matrix[x][0] = x

    # Fill in matrix
    for i in xrange(1, size*size + 1):
        for j in xrange(1, size*size + 1):
            matrix[i][j] = fn(i, j)

    print_matrix(matrix)


size = 3

setup_boot_times(size)
create_grid(size)
setup_noise_model(size)

print
show_network_matrix(size)
print
show_node_relation_matrix(r.connected)
print
show_node_relation_matrix(r.gain)
print

t.runNextEvent()
time = t.time()
while time + (20 * t.ticksPerSecond()) > t.time():
    t.runNextEvent()
"""
