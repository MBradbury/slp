
from Simulator import *

class Attacker(object):
    def __init__(self, sim, sourceId, startNodeId):
        self.sim = sim

        out = OutputCatcher(self.process)
        self.sim.tossim.addChannel('Attacker-RCV', out.write)

        self.sim.addOutputProcessor(out)

        self.sourceId = sourceId
        self.position = None

        self.move(startNodeId)

        self.moves = 0

    def foundSourceSlow(self):
        return self.position == self.sourceId

    def foundSource(self):
        return self.hasFoundSource

    def move(self, to):
        self.position = to
        self.hasFoundSource = self.foundSourceSlow()

        self.moves += 1

    def draw(self, time, nodeID):
        if not hasattr(self.sim, "scene"):
            return

        (x,y) = self.sim.getNodeLocation(nodeID)

        shapeId = "attacker"

        color = '1,0,0'

        options = 'line=LineStyle(color=(%s)),fill=FillStyle(color=(%s))' % (color,color)

        self.sim.scene.execute(time, 'delshape("%s")' % shapeId)
        self.sim.scene.execute(time, 'circle(%d,%d,5,id="%s",%s)' % (x,y,shapeId,options))

    def process_line(self, line):
        (time, msgType, nodeID, fromID, seqNo) = line.split(',')

        time = float(time) / self.sim.tossim.ticksPerSecond() # Get time to be in sec
        nodeID = int(nodeID)
        fromID = int(fromID)
        seqNo = int(seqNo)

        return (time, msgType, nodeID, fromID, seqNo)


class BasicReactiveAttacker(Attacker):
    def process(self, line):
        # Don't want to move if the source has been found
        if self.foundSource():
            return

        (time, msgType, nodeID, fromID, seqNo) = self.process_line(line)

        if self.position == nodeID:

            self.move(fromID)

            #print("Attacker moved from {} to {}".format(nodeID, fromID))

            self.draw(time, self.position)

class IgnorePreviousLocationReactiveAttacker(Attacker):
    def __init__(self, sim, sourceId, startNodeId):
        super(IgnorePreviousLocationReactiveAttacker, self).__init__(sim, sourceId, startNodeId)
        self.previousLocation = None

    def process(self, line):
        # Don't want to move if the source has been found
        if self.foundSource():
            return

        (time, msgType, nodeID, fromID, seqNo) = self.process_line(line)

        if self.position == nodeID and self.previousLocation != fromID:

            self.move(fromID)

            #print("Attacker moved from {} to {}".format(nodeID, fromID))

            self.draw(time, self.position)

    def move(self, to):
        self.previousLocation = self.position
        super(IgnorePreviousLocationReactiveAttacker, self).move(to)

class SeqNoReactiveAttacker(Attacker):
    def __init__(self, sim, sourceId, startNodeId):
        super(SeqNoReactiveAttacker, self).__init__(sim, sourceId, startNodeId)
        self.seqNos = {}

    def process(self, line):
        # Don't want to move if the source has been found
        if self.foundSource():
            return

        (time, msgType, nodeID, fromID, seqNo) = self.process_line(line)

        if self.position == nodeID and (msgType not in self.seqNos or self.seqNos[msgType] < seqNo):

            self.seqNos[msgType] = seqNo
            
            self.move(fromID)

            #print("Attacker moved from {} to {}".format(nodeID, fromID))

            self.draw(time, self.position)

def models():
    return [cls.__name__ for cls in Attacker.__subclasses__()]

def default():
    return SeqNoReactiveAttacker.__name__
