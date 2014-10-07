import math, getopt, re
import sys, os, time, select, heapq
from random import random
from TOSSIM import *
from topovis import *
from topovis.TkPlotter import Plotter

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
class Node:
   def __init__(self,id,location,tossim_node):
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

###############################################
class TosVis(object):
   ####################
   def __init__(self, node_locations, range, drawNeighborLinks=True):
      self.tossim = Tossim([])

      self.range = range
      self.drawNeighborLinks = drawNeighborLinks
      self.createNodes(node_locations)
      self.debug_analyzer = DebugAnalyzer()
      self.am_types = None
      self.evq = []   # custom event queue

      # Randomly set the boot times for all nodes
      for n in self.nodes:
         self.setBootTime(n)

      # setup a pipe for monitoring dbg messages
      dbg = OutputCatcher(self.processDbgMsg)
      self.tossim.addChannel('LedsC', dbg.write)
      self.tossim.addChannel('AM', dbg.write)

      self.outProcs = []
      self.addOutputProcessor(dbg)


   def addOutputProcessor(self, op):
      self.outProcs.append(op)

   ####################
   def simTime(self):
      'Returns the current simulation time in seconds'
      return float(self.tossim.time())/self.tossim.ticksPerSecond()

   ####################
   def createNodes(self, node_locations):
      "Creates nodes and initialize their boot times"
      self.nodes = []
      for i,loc in enumerate(node_locations):
         tossim_node = self.tossim.getNode(i)
         new_node = Node(i, loc, tossim_node)
         self.createNoiseModel(new_node)
         self.nodes.append(new_node)

   ####################
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
                  if self.drawNeighborLinks:
                     self.scene.execute(0, 'addlink(%d,%d,1)' % (i,j))

   ####################
   def createNoiseModel(self, node):
      for i in range(100):
         node.tossim_node.addNoiseTraceReading(int(random()*20)-100)
      node.tossim_node.createNoiseModel()

   ####################
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

   ####################
   def setBootTime(self, node):
      node.tossim_node.bootAtTime(int(random() * self.tossim.ticksPerSecond()))

   ####################
   def moveNode(self, node, location, time=None):
      '''
      Schedules the specified node to move to the new location at the
      specified time.  If time is omitted, move the node immediately.
      '''
      # This function requires access to the simulation queue.  TOSSIM must be
      # patched for it to work
      raise NotImplementedError("Need TOSSIM patching")

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
      (id,cmp,detail) = result
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
   def continuePredicate(self):
      return True

   ####################
   def run(self):
      'Starts simulation with visualization'
      # Setup an animating canvas
      scene = Scene(timescale=1)
      tkplot = Plotter()
      self.scene = scene
      self.tkplot = tkplot
      scene.addPlotter(tkplot)

      # set line style used for neighbor relationship
      scene.execute(0, 'linestyle(1,color=(.7,.7,.7))')

      # draw nodes on animating canvas
      for n in self.nodes:
         scene.execute(0, 'node(%d,%f,%f)' % (n.id, n.location[0], n.location[1]))

      self.setupRadio()

      # Start simulation
      while self.continuePredicate():
         if self.tossim.runNextEvent() == 0:
            break

         for op in self.outProcs:
            op.process()

###############################################
