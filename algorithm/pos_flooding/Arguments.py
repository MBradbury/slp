
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

        self.add_argument("--deactivate-period", type=self.type_positive_float, required=True)

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result["DEACTIVATE_PERIOD_MS"] = int(self.args.deactivate_period * 1000)

        return result
