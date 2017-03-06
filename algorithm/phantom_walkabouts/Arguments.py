
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.SourcePeriodModel
import simulator.MobilityModel

order_choices = ["LongShort", "ShortLong"]

class Arguments(ArgumentsCommon):
    def __init__(self):
        super(Arguments, self).__init__("SLP Phantom_Walkabouts_dynamic",
            has_safety_period=True, has_safety_factor=True)

        self.add_argument("--source-period",
                          type=simulator.SourcePeriodModel.eval_input, required=True)
        self.add_argument("--source-mobility",
                          type=simulator.MobilityModel.eval_input,
                          default=simulator.MobilityModel.StationaryMobilityModel())

        self.add_argument("--wait-before-short", type=self.type_positive_int, required=True)

        self.add_argument("--direction-bias", type=self.type_probability, required=False, default=0.9)

        self.add_argument("--order", type=str, choices=order_choices, required=True)

        self.add_argument("--short-count", type=self.type_positive_int, required=True)
        self.add_argument("--long-count", type=self.type_positive_int, required=True)


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

        result["SHORT_COUNT"] = int(self.args.short_count)
        result["LONG_COUNT"] = int(self.args.long_count)

        return result
