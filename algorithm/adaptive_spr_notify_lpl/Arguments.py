
from algorithm.adaptive_spr_notify.Arguments import Arguments as ArgumentsCommon

class Arguments(ArgumentsCommon):
    def __init__(self):
        super().__init__()

        self.add_argument("--lpl-choose-early", type=self.type_positive_int, required=True) #   5
        self.add_argument("--lpl-choose-late", type=self.type_positive_int, required=True)  #  40
        self.add_argument("--lpl-normal-early", type=self.type_positive_int, required=True) #  40
        self.add_argument("--lpl-normal-late", type=self.type_positive_int, required=True)  #  40
        self.add_argument("--lpl-fake-early", type=self.type_positive_int, required=True)   # 100
        self.add_argument("--lpl-fake-late", type=self.type_positive_int, required=True)    # 150

    def parse(self, argv):
        super().parse(argv)

        # Need to force these values
        setattr(self.args, "low_power_listening", "enabled")
        setattr(self.args, "lpl_custom", "SLPDutyCycleC")

    def build_arguments(self):
        result = super().build_arguments()

        result["SLP_LPL_CHOOSE_EARLY_MS"] = self.args.lpl_choose_early
        result["SLP_LPL_CHOOSE_LATE_MS"] = self.args.lpl_choose_late
        result["SLP_LPL_NORMAL_EARLY_MS"] = self.args.lpl_normal_early
        result["SLP_LPL_NORMAL_LATE_MS"] = self.args.lpl_normal_late
        result["SLP_LPL_FAKE_EARLY_MS"] = self.args.lpl_fake_early
        result["SLP_LPL_FAKE_LATE_MS"] = self.args.lpl_fake_late

        return result
