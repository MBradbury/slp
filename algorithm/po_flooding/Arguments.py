
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.SourcePeriodModel
import simulator.MobilityModel

CONE_TYPE_OPTIONS = ("WITH_SNOOP", "WITHOUT_SNOOP")

class Arguments(ArgumentsCommon):
    def __init__(self):
        super(Arguments, self).__init__("SLP Power Off Flooding", has_safety_period=True)

        self.add_argument("--source-period",
                          type=simulator.SourcePeriodModel.eval_input, required=True)
        self.add_argument("--source-mobility",
                          type=simulator.MobilityModel.eval_input,
                          default=simulator.MobilityModel.StationaryMobilityModel())

        self.add_argument("--protected-sink-hops", type=self.type_positive_int, required=True)
        self.add_argument("--activate-period", type=self.type_positive_float, required=True)
        self.add_argument("--cone-type", type=str, choices=CONE_TYPE_OPTIONS, required=True)
        self.add_argument("--expiry-delay-factor", type=self.type_positive_float, required=True)

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result["PROTECTED_SINK_HOPS"] = self.args.protected_sink_hops
        result["ACTIVATE_PERIOD_MS"] = int(self.args.activate_period * 1000)
        result["ACTIVATE_EXPIRY_PERIOD_MS"] = int(self.args.activate_period * 1000 * self.args.expiry_delay_factor)
        result["CONE_TYPE_" + self.args.cone_type] = 1

        return result
