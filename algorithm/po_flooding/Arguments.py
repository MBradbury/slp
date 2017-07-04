
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.SourcePeriodModel
import simulator.MobilityModel

class Arguments(ArgumentsCommon):
    def __init__(self):
        super(Arguments, self).__init__("SLP Power Off Flooding", has_safety_period=True)

        self.add_argument("--source-period",
            type=simulator.SourcePeriodModel.eval_input, required=True)
        self.add_argument("--source-mobility",
            type=simulator.MobilityModel.eval_input,
            default=simulator.MobilityModel.StationaryMobilityModel())

        self.add_argument("--protected-sink-hops", type=self.type_positive_int, required=True)
        self.add_argument("--cone-width", type=self.type_positive_int, required=True)

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result["PROTECTED_SINK_HOPS"] = self.args.protected_sink_hops
        result["CONE_WIDTH"] = self.args.cone_width

        return result
