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

dynamic_repeat_choices = ["single", "multiple"]

class Arguments(ArgumentsCommon):
    def __init__(self):
        super(Arguments, self).__init__("SLP Phantom_Walkabouts_dynamic_rwc", has_safety_period=True)

        self.add_argument("--source-period",
                          type=simulator.SourcePeriodModel.eval_input, required=True)
        self.add_argument("--source-mobility",
                          type=simulator.MobilityModel.eval_input,
                          default=simulator.MobilityModel.StationaryMobilityModel())

        self.add_argument("--wait-before-short", type=int, required=True)

        self.add_argument("--direction-bias", type=restricted_float, required=False, default=0.9)

        self.add_argument("--order", type=str, choices=order_choices, required=True)

        self.add_argument("--dynamic-period-repeat", choices=dynamic_repeat_choices, required=True)

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result["BIASED_NO"] = int(self.args.direction_bias * 100)

        result["BOTTOM_LEFT_NODE_ID"] = self._get_node_id("bottom_left")
        result["BOTTOM_RIGHT_NODE_ID"] = self._get_node_id("bottom_right")
        result["TOP_LEFT_NODE_ID"] = self._get_node_id("top_left")
        result["TOP_RIGHT_NODE_ID"] = self._get_node_id("top_right")

        result["WAIT_BEFORE_SHORT_MS"] = int(self.args.wait_before_short)

        if self.args.order == "LongShort":
            result["LOND_SHORT_SEQUENCE"] = 0
        else:
            result["SHORT_LONG_SEQUENCE"] = 0

        if self.args.dynamic_period_repeat == "single":
            result["DYNAMIC_PERIOD_SINGLE"] = 0
        else:
            result["DYNAMIC_PERIOD_MULTIPLE"] = 0

        return result
