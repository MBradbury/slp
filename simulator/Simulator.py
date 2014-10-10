from random import random
import os, sys, math, select

class Node:
	def __init__(self, id, location, tossim_node):
		self.id = id
		self.location = location
		self.tossim_node = tossim_node

class OutputCatcher:
	def __init__(self, linefn):
		(r, w) = os.pipe()
		self.read = os.fdopen(r, 'r')
		self.write = os.fdopen(w, 'w')
		self.linefn = linefn

	def process(self):
		while True:
			r,w,e = select.select([self.read.fileno()],[],[],0)
			if len(r) == 1:
				line = self.read.readline()
				self.linefn(line)
			else:
				break

	def close(self):
		self.read.close()
		self.write.close()

class Simulator(object):
	def __init__(self, TOSSIM, node_locations, range, seed=None):
		self.tossim = TOSSIM.Tossim([])

		self.outProcs = []

		if seed is not None:
			self.tossim.randomSeed(seed)
		self.seed = seed

		self.range = range

		self.createNodes(node_locations)

		# Randomly set the boot times for all nodes
		for n in self.nodes:
			self.setBootTime(n)

	def __enter__(self):
		return self

	def __exit__(self, type, value, tb):
		for op in self.outProcs:
			op.close()

	def setBootTime(self, node):
		pass

	def addOutputProcessor(self, op):
		self.outProcs.append(op)

	def simTime(self):
		'Returns the current simulation time in seconds'
		return float(self.tossim.time())/self.tossim.ticksPerSecond()

	def createNodes(self, node_locations):
		"Creates nodes and initialize their boot times"
		self.nodes = []
		for i,loc in enumerate(node_locations):
			tossim_node = self.tossim.getNode(i)
			new_node = Node(i, loc, tossim_node)
			self.createNoiseModel(new_node)
			self.nodes.append(new_node)

	def setupRadio(self):
		"Creates radio links for node pairs that are in range"
		radio = self.tossim.radio()
		num_nodes = len(self.nodes)
		for i,ni in enumerate(self.nodes):
			for j,nj in enumerate(self.nodes):
				if i != j:
					(isLinked, gain) = self.computeRFGain(ni, nj)
					if isLinked:
						radio.add(i, j, gain)
						#if self.drawNeighborLinks:
						#	self.scene.execute(0, 'addlink(%d,%d,1)' % (i,j))

	def createNoiseModel(self, node):
		for i in range(100):
			node.tossim_node.addNoiseTraceReading(int(random()*20)-100)
		node.tossim_node.createNoiseModel()

	def computeRFGain(self, src, dst):
		'''
		Returns signal reception gain between src and dst using a simple
		range-threshold model.  Should be overriden with a more realistic
		propagation model.
		'''
		if src == dst:
			return (False, 0)

		(x1,y1) = src.location
		(x2,y2) = dst.location
		dx = x1 - x2;
		dy = y1 - y2;
		if math.sqrt(dx*dx + dy*dy) <= self.range:
			return (True, 0)
		else:
			return (False, 0)

	def setBootTime(self, node):
		node.tossim_node.bootAtTime(int(random() * self.tossim.ticksPerSecond()))

	def moveNode(self, node, location, time=None):
		'''
		Schedules the specified node to move to the new location at the
		specified time.  If time is omitted, move the node immediately.
		'''
		# This function requires access to the simulation queue.  TOSSIM must be
		# patched for it to work
		raise NotImplementedError("Need TOSSIM patching")

	def continuePredicate(self):
		return True

	def preRun(self):
		self.setupRadio()

	def postRun(self):
		pass

	def inRun(self):
		for op in self.outProcs:
			op.process()

	def run(self):
		
		self.preRun()

		while self.continuePredicate():
			if self.tossim.runNextEvent() == 0:
				break

			self.inRun()

		self.postRun()

