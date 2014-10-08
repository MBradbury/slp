
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

        self.moves = 0

    def foundSource(self):
        return self.position == self.sourceId

    def process(self, line):
        # Don't want to move if the source has been found
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

            self.moves += 1

            #print("Attacker moved from {} to {}".format(nodeID, fromID))

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
