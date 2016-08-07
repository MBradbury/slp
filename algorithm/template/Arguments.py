import argparse

from simulator.ArgumentsCommon import ArgumentsCommon

def restricted_float(x):
    x = float(x)
    if x < 0.0 or x > 1.0:
        raise argparse.ArgumentTypeError("{} not in range [0.0, 1.0]".format(x))
    return x

class Arguments(ArgumentsCommon):
    def __init__(self):
        super(Arguments, self).__init__("SLP Template", has_safety_period=True)

        self.add_argument("--source-period", type=float, required=True)
        self.add_argument("--fake-period", type=float, required=True)
        self.add_argument("--temp-fake-duration", type=float, required=True)

        self.add_argument("--pr-tfs", type=restricted_float, required=True)
        self.add_argument("--pr-pfs", type=restricted_float, required=True)

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result.update({
            "FAKE_PERIOD_MS": int(self.args.fake_period * 1000),
            "TEMP_FAKE_DURATION_MS": int(self.args.temp_fake_duration * 1000),
            "PR_TFS": self.args.pr_tfs,
            "PR_PFS": self.args.pr_pfs
        })

        return result
