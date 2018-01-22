
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.MobilityModel

approaches = ("PB_FIXED1_APPROACH", "PB_FIXED2_APPROACH", "PB_RND_APPROACH")

class Arguments(ArgumentsCommon):
    def __init__(self):
        super().__init__("SLP Adaptive SPR Notify", has_safety_period=True)

        self.add_argument("--source-period", type=self.type_positive_float, required=True)
        self.add_argument("--source-mobility",
                          type=simulator.MobilityModel.eval_input,
                          default=simulator.MobilityModel.StationaryMobilityModel())

        self.add_argument("--approach", type=str, choices=approaches, required=True)

        self.add_argument("--lpl-choose-early", type=self.type_positive_float, required=False, default=None) # 0.005
        self.add_argument("--lpl-choose-late", type=self.type_positive_float, required=False, default=None)  # 0.040
        self.add_argument("--lpl-normal-early", type=self.type_positive_float, required=False, default=None) # 0.040
        self.add_argument("--lpl-normal-late", type=self.type_positive_float, required=False, default=None)  # 0.040
        self.add_argument("--lpl-fake-early", type=self.type_positive_float, required=False, default=None)   # 0.100
        self.add_argument("--lpl-fake-late", type=self.type_positive_float, required=False, default=None)    # 0.150

    def build_arguments(self):
        result = super().build_arguments()

        result["APPROACH"] = self.args.approach
        result[self.args.approach] = 1

        if getattr(self.args, "low_power_listening", "disabled") == "enabled" and getattr(self.args, "lpl_custom", "") == "SLPDutyCycleC":
            result["SLP_LPL_CHOOSE_EARLY_MS"] = int(self.args.lpl_choose_early * 1000)
            result["SLP_LPL_CHOOSE_LATE_MS"] = int(self.args.lpl_choose_late * 1000)
            result["SLP_LPL_NORMAL_EARLY_MS"] = int(self.args.lpl_normal_early * 1000)
            result["SLP_LPL_NORMAL_LATE_MS"] = int(self.args.lpl_normal_late * 1000)
            result["SLP_LPL_FAKE_EARLY_MS"] = int(self.args.lpl_fake_early * 1000)
            result["SLP_LPL_FAKE_LATE_MS"] = int(self.args.lpl_fake_late * 1000)

        return result
