import os, struct, importlib

from simulator.TosVis import TosVis

class Simulation(TosVis):
    def __init__(self, moduleName, configuration, args):

        super(Simulation, self).__init__(
            importlib.import_module('{}.TOSSIM'.format(moduleName)),
            node_locations=configuration.topology.nodes,
            range=args.wireless_range,
            seed=args.seed if args.seed is not None else self.secureRandom()
            )

        self.safetyPeriod = args.safety_period if hasattr(args, "safety_period") else None

#       self.tossim.addChannel("Metric-BCAST-Normal", sys.stdout)
#       self.tossim.addChannel("Metric-RCV-Normal", sys.stdout)
#       self.tossim.addChannel("Boot", sys.stdout)
#       self.tossim.addChannel("SourceBroadcasterC", sys.stdout)
#       self.tossim.addChannel("Attacker-RCV", sys.stdout)

        self.attackers = []

        Metrics = importlib.import_module('{}.Metrics'.format(moduleName))

        self.metrics = Metrics.Metrics(self, configuration.sourceId, configuration.sinkId)

    def addAttacker(self, attacker):
        self.attackers.append(attacker)

    def continuePredicate(self):
        return not self.anyAttackerFoundSource() and (self.safetyPeriod is None or self.simTime() < self.safetyPeriod)

    def anyAttackerFoundSource(self):
        return any(attacker.foundSource() for attacker in self.attackers)

    @staticmethod
    def secureRandom():
        return struct.unpack("<i", os.urandom(4))[0]
