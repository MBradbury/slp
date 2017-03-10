
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.SourcePeriodModel
import simulator.MobilityModel

class Arguments(ArgumentsCommon):
    def __init__(self):
        super(Arguments, self).__init__("SLP Protectionless", has_safety_period=False)

        self.add_argument("--source-period",
            type=simulator.SourcePeriodModel.eval_input, required=True)
        self.add_argument("--source-mobility",
            type=simulator.MobilityModel.eval_input,
            default=simulator.MobilityModel.StationaryMobilityModel())

        self.add_argument("--gossip-period", type=int, required=True)

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result["GOSSIP_PERIOD_MS"] = self.args.gossip_period

        return result
