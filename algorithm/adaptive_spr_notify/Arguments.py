
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.MobilityModel

approaches = ("PB_FIXED1_APPROACH", "PB_FIXED2_APPROACH", "PB_RND_APPROACH")

class Arguments(ArgumentsCommon):
    def __init__(self, **kwargs):
        super().__init__("SLP Adaptive SPR Notify", has_safety_period=True, **kwargs)

        self.add_argument("--source-period", type=self.type_positive_float, required=True)
        self.add_argument("--source-mobility",
                          type=simulator.MobilityModel.eval_input,
                          default=simulator.MobilityModel.StationaryMobilityModel())

        self.add_argument("--approach", type=str, choices=approaches, required=True)

    def build_arguments(self):
        result = super().build_arguments()

        result["APPROACH"] = self.args.approach
        result[self.args.approach] = 1

        return result
