import importlib

from simulator.TosVis import TosVis

class Simulation(TosVis):
    def __init__(self, moduleName, seed, configuration, range, safetyPeriod=float('inf')):

        super(Simulation, self).__init__(
            importlib.import_module('{}.TOSSIM'.format(moduleName)),
            node_locations=configuration.topology.nodes,
            range=range,
            seed=seed
            )

        self.safetyPeriod = safetyPeriod

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
        return not self.anyAttackerFoundSource() and self.simTime() < self.safetyPeriod

    def anyAttackerFoundSource(self):
        return any(attacker.foundSource() for attacker in self.attackers)
