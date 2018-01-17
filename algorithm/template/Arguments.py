
from simulator.ArgumentsCommon import ArgumentsCommon

class Arguments(ArgumentsCommon):
    def __init__(self):
        super().__init__("SLP Template", has_safety_period=True)

        self.add_argument("--source-period", type=self.type_positive_float, required=True)
        self.add_argument("--fake-period", type=self.type_positive_float, required=True)
        self.add_argument("--temp-fake-duration", type=self.type_positive_float, required=True)

        self.add_argument("--pr-tfs", type=self.type_probability, required=True)
        self.add_argument("--pr-pfs", type=self.type_probability, required=True)

    def build_arguments(self):
        result = super().build_arguments()

        result.update({
            "FAKE_PERIOD_MS": int(self.args.fake_period * 1000),
            "TEMP_FAKE_DURATION_MS": int(self.args.temp_fake_duration * 1000),
            "PR_TFS": self.args.pr_tfs,
            "PR_PFS": self.args.pr_pfs,
        })

        return result
