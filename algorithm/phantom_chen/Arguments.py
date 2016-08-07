import argparse
import math

from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.SourcePeriodModel
import simulator.MobilityModel
import simulator.Configuration as Configuration
import simulator.Topology as Topology

def restricted_float(x):
    x = float(x)
    if x < 0.0 or x > 1.0:
        raise argparse.ArgumentTypeError("{} not in range [0.0, 1.0]".format(x))
    return x

order_choices = ["LongShort", "ShortLong"]

class Arguments(ArgumentsCommon):
    def __init__(self):
        super(Arguments, self).__init__("SLP Phantom (Chen's)", has_safety_period=True)

        self.add_argument("--source-period",
                          type=simulator.SourcePeriodModel.eval_input, required=True)
        self.add_argument("--source-mobility",
                          type=simulator.MobilityModel.eval_input,
                          default=simulator.MobilityModel.StationaryMobilityModel())

        self.add_argument("--short-walk-length", type=int, required=True)
        self.add_argument("--long-walk-length", type=int, required=True)

        self.add_argument("--wait-before-short", type=int, required=True)

        self.add_argument("--direction-bias", type=restricted_float, required=False, default=0.9)

        self.add_argument("--order", type=str, choices=order_choices, required=True)

        self.add_argument("--short-count", type=int, required=True)
        self.add_argument("--long-count", type=int, required=True)

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result["RANDOM_WALK_HOPS"] = int(self.args.short_walk_length)
        result["LONG_RANDOM_WALK_HOPS"] = int(self.args.long_walk_length)

        configuration = Configuration.create(self.args.configuration, self.args)

        if not isinstance(configuration.topology, Topology.Grid):
            raise RuntimeError("Topology must be a grid")

        result["TOPOLOGY_SIZE"] = int(math.sqrt(len(configuration.topology.nodes)))

        result["WAIT_BEFORE_SHORT_MS"] = int(self.args.wait_before_short)

        result["Biased_No"] = int(self.args.direction_bias * 100)

        if self.args.order == "LongShort":
            result["LOND_SHORT_SEQUENCE"] = 0
        else:
            result["SHORT_LONG_SEQUENCE"] = 0

        result["SHORT_COUNT"] = int(self.args.short_count)
        result["LONG_COUNT"] = int(self.args.long_count)

        return result
