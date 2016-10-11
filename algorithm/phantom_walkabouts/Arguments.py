import argparse
import math

from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.SourcePeriodModel
import simulator.MobilityModel
import simulator.Configuration as Configuration

def restricted_float(x):
    x = float(x)
    if x < 0.0 or x > 1.0:
        raise argparse.ArgumentTypeError("{} not in range [0.0, 1.0]".format(x))
    return x

order_choices = ["LongShort", "ShortLong"]

class Arguments(ArgumentsCommon):
    def __init__(self):
        super(Arguments, self).__init__("SLP Phantom_Walkabouts", has_safety_period=True)

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

        self.add_argument("--landmark-node", default="sink_id")

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result["RANDOM_WALK_HOPS"] = int(self.args.short_walk_length)
        result["LONG_RANDOM_WALK_HOPS"] = int(self.args.long_walk_length)

        result["LANDMARK_NODE_ID"] = self._get_node_id(self.args.landmark_node)

        result["Biased_No"] = int(self.args.direction_bias *100)

        configuration = Configuration.create(self.args.configuration, self.args)

        result["BOTTOM_LEFT_NODE_ID"] = configuration.topology.bottom_left

        result["BOTTOM_RIGHT_NODE_ID"] = configuration.topology.bottom_near_right

        result["TOP_LEFT_NODE_ID"] = configuration.topology.top_left

        result["TOP_RIGHT_NODE_ID"] = configuration.topology.top_right

        result["WAIT_BEFORE_SHORT_MS"] = int(self.args.wait_before_short)

        if self.args.order == "LongShort":
            result["LOND_SHORT_SEQUENCE"] = 0
        else:
            result["SHORT_LONG_SEQUENCE"] = 0

        result["SHORT_COUNT"] = int(self.args.short_count)
        result["LONG_COUNT"] = int(self.args.long_count)

        return result
