from __future__ import print_function
import os, struct, importlib, subprocess, sys

from simulator.TosVis import TosVis
from simulator.Topology import topology_path

class Simulation(TosVis):
    def __init__(self, moduleName, configuration, args):

        super(Simulation, self).__init__(
            importlib.import_module('{}.TOSSIM'.format(moduleName)),
            node_locations=configuration.topology.nodes,
            range=args.distance,
            seed=args.seed if args.seed is not None else self.secureRandom()
            )

        self.safetyPeriod = args.safety_period if hasattr(args, "safety_period") else None

#        self.tossim.addChannel("Fake-Probability-Decision", sys.stdout)
#        self.tossim.addChannel("stdout", sys.stdout)
#        self.tossim.addChannel("Metric-BCAST-Normal", sys.stdout)
#        self.tossim.addChannel("Metric-RCV-Normal", sys.stdout)
#        self.tossim.addChannel("Boot", sys.stdout)
#        self.tossim.addChannel("SourceBroadcasterC", sys.stdout)
#        self.tossim.addChannel("Attacker-RCV", sys.stdout)

        self.attackers = []

        Metrics = importlib.import_module('{}.Metrics'.format(moduleName))

        self.metrics = Metrics.Metrics(self, configuration)

        self.topologyPath = topology_path(moduleName, args)

    @staticmethod
    def writeTopologyFile(node_locations, location="."):
        with open(os.path.join(location, "topology.txt"), "w") as f:
            for i,loc in enumerate(node_locations):
                print("{}\t{}\t{}".format(i, loc[0], loc[1]), file=f) 

    def setupRadio(self):
        output = subprocess.check_output(
            "java -cp ./tinyos/support/sdk/java/net/tinyos/sim LinkLayerModel model.txt {} {}".format(self.topologyPath, self.seed),
            shell=True)

        for line in output.splitlines():
            parts = line.strip().split("\t")

            if parts[0] == "gain":
                (g, nodeIdFrom, nodeIdTo, gain) = parts

                self.radio.add(int(nodeIdFrom), int(nodeIdTo), float(gain))

            elif parts[0] == "noise":
                (n, nodeId, noiseFloor, awgn) = parts

                self.radio.setNoise(int(nodeId), float(noiseFloor), float(awgn))

    def setupNoiseModels(self):
        path = "meyer-heavy.txt"

        # Instead of reading in all the noise data, a limited amount
        # is used. If we were to use it all it leads to large slowdowns.
        count = 1000

        noises = [noise for _, noise in zip(range(count), self.readNoiseFromFile(path))]
        
        for node in self.nodes:
            for noise in noises:
                node.tossim_node.addNoiseTraceReading(noise)
            node.tossim_node.createNoiseModel()

    def addAttacker(self, attacker):
        self.attackers.append(attacker)

    def continuePredicate(self):
        return not self.anyAttackerFoundSource() and (self.safetyPeriod is None or self.simTime() < self.safetyPeriod)

    def anyAttackerFoundSource(self):
        return any(attacker.foundSource() for attacker in self.attackers)

    @staticmethod
    def secureRandom():
        return struct.unpack("<i", os.urandom(4))[0]
