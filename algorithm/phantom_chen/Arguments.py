import argparse, math
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.SourcePeriodModel
import simulator.MobilityModel
import simulator.Configuration as Configuration
import simulator.Topology as Topology

class Arguments(ArgumentsCommon):
    def __init__(self):
        parser = argparse.ArgumentParser(description="SLP Phantom (Chen's)", add_help=True)
        super(Arguments, self).__init__(parser, has_safety_period=True)

        parser.add_argument("--source-period",
            type=simulator.SourcePeriodModel.eval_input, required=True)
        parser.add_argument("--source-mobility",
            type=simulator.MobilityModel.eval_input,
            default=simulator.MobilityModel.StationaryMobilityModel())

        parser.add_argument("--short-walk-length", type=int, required=True)
        parser.add_argument("--long-walk-length", type=int, required=True)

        #parser.add_argument("--wait-before-short", type=int, required=True)

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result["RANDOM_WALK_HOPS"] = int(self.args.short_walk_length)
        result["LONG_RANDOM_WALK_HOPS"] = int(self.args.long_walk_length)

        configuration = Configuration.create(self.args.configuration, self.args)

        if not isinstance(configuration.topology, Topology.Grid):
            raise RuntimeError("Topology must be a grid")

        result["TOPOLOGY_SIZE"] = int(math.sqrt(len(configuration.topology.nodes)))

        #result["WAIT_BEFORE_SHORT_MS"] = int(self.args.wait_before_short)

        return result
