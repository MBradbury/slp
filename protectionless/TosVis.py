import math, getopt, re
import sys, os, time, select, heapq
from topovis import *
from topovis.TkPlotter import Plotter

from Simulator import *

###############################################
class DebugAnalyzer:
	LED     = 0
	AM_SEND = 1
	AM_RECV = 2

	WHOLE_RE  = re.compile(r'DEBUG \((\d+)\): (.*)')
	LED_RE    = re.compile(r'LEDS: Led(\d) (.*)\.')
	AMSEND_RE = re.compile(r'AM: Sending packet \(id=(\d+), len=(\d+)\) to (\d+)')
	AMRECV_RE = re.compile(r'Received active message \(0x[0-9a-f]*\) of type (\d+) and length (\d+)')

	####################
	def analyze(self, dbg):
		match = self.WHOLE_RE.match(dbg)
		if match is None:
			return None

		id = int(match.group(1))
		detail = match.group(2)

		# LED message
		match = self.LED_RE.match(detail)
		if match is not None:
			ledno = int(match.group(1))
			stateStr = match.group(2)
			if stateStr == 'off':
				state = 0
			else:
				state = 1
			return (id, self.LED, (ledno,state))

		# AM Send message
		match = self.AMSEND_RE.match(detail)
		if match is not None:
			amtype = int(match.group(1))
			amlen  = int(match.group(2))
			amdst  = int(match.group(3))
			return (id, self.AM_SEND, (amtype,amlen,amdst))

		# AM Receive message
		match = self.AMRECV_RE.match(detail)
		if match is not None:
			amtype = int(match.group(1))
			amlen  = int(match.group(2))
			return (id, self.AM_RECV, (amtype,amlen))

		return None

###############################################
class TosVis(Simulator):
	####################
	def __init__(self, node_locations, range, drawNeighborLinks=True):

		super(TosVis, self).__init__(
			node_locations=node_locations,
			range=range)

		self.drawNeighborLinks = drawNeighborLinks
		self.debug_analyzer = DebugAnalyzer()
		self.am_types = None
		self.evq = []   # custom event queue

		# setup a pipe for monitoring dbg messages
		dbg = OutputCatcher(self.processDbgMsg)
		self.tossim.addChannel('LedsC', dbg.write)
		self.tossim.addChannel('AM', dbg.write)

		self.addOutputProcessor(dbg)

	####################
	def animateLeds(self,time,id,ledno,state):
		scene = self.scene
		(x,y) = self.nodes[id].location
		shape_id = '%d:%d' % (id,ledno)
		if state == 0:
			scene.execute(time, 'delshape("%s")' % shape_id)
			return
		if ledno == 0:
			x,y = x+5,y+5
			color = '1,0,0'
		elif ledno == 1:
			x,y = x,y+5
			color = '0,.8,0'
		else:
			x,y = x-5,y+5
			color = '0,0,1'
		options = 'line=LineStyle(color=(%s)),fill=FillStyle(color=(%s))' % (color,color)
		scene.execute(time, 'circle(%d,%d,2,id="%s",%s)' % (x,y,shape_id,options))

	####################
	def animateAmSend(self,time,sender,amtype,amlen,amdst):
		if self.am_types is not None and amtype not in self.am_types:
			return
		scene = self.scene
		(x,y) = self.nodes[sender].location
		scene.execute(time,
				'circle(%d,%d,%d,line=LineStyle(color=(1,0,0),dash=(1,1)),delay=.3)'
				% (x,y,self.range))

	####################
	def animateAmRecv(self,time,receiver,amtype,amlen):
		if self.am_types is not None and amtype not in self.am_types:
			return
		scene = self.scene
		(x,y) = self.nodes[receiver].location
		scene.execute(time,
				'circle(%d,%d,%d,line=LineStyle(color=(0,0,1),width=3),delay=.3)'
				% (x,y,10))

	####################
	def processDbgMsg(self, dbg):
		result = self.debug_analyzer.analyze(dbg)
		if result is None:
			return
		(id, cmp, detail) = result
		if cmp == DebugAnalyzer.LED:
			(ledno, state) = detail
			self.animateLeds(self.simTime(), id, ledno, state)
		elif cmp == DebugAnalyzer.AM_SEND:
			(amtype,amlen,amdst) = detail
			self.animateAmSend(self.simTime(), id, amtype, amlen, amdst)
		elif cmp == DebugAnalyzer.AM_RECV:
			(amtype,amlen) = detail
			self.animateAmRecv(self.simTime(), id, amtype, amlen)

	####################
	def preRun(self):
		super(TosVis, self).preRun()

		# Setup an animating canvas
		self.scene = Scene(timescale=1)
		self.tkplot = Plotter()
		self.scene.addPlotter(self.tkplot)

		# set line style used for neighbor relationship
		self.scene.execute(0, 'linestyle(1,color=(.7,.7,.7))')

		# draw nodes on animating canvas
		for n in self.nodes:
			self.scene.execute(0, 'node(%d,%f,%f)' % (n.id, n.location[0], n.location[1]))

###############################################
