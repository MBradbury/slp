
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.MobilityModel

approaches = ["PB_FIXED1_APPROACH", "PB_FIXED2_APPROACH", "PB_RND_APPROACH"]

class Arguments(ArgumentsCommon):
    def __init__(self):
        super(Arguments, self).__init__("SLP Adaptive SPR CTP", has_safety_period=True)

        self.add_argument("--source-period", type=float, required=True)
        self.add_argument("--source-mobility",
                            type=simulator.MobilityModel.eval_input,
                            default=simulator.MobilityModel.StationaryMobilityModel())

        self.add_argument("--approach", type=str, choices=approaches, required=True)

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result.update({
            "APPROACH": self.args.approach,
            self.args.approach: 1,
        })

        return result
