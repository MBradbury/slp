import argparse

from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.MobilityModel

def restricted_float(x):
    x = float(x)
    if x < 0.0 or x > 1.0:
        raise argparse.ArgumentTypeError("{} not in range [0.0, 1.0]".format(x))
    return x

class Arguments(ArgumentsCommon):
    def __init__(self):
        super(Arguments, self).__init__("SLP Short Lived Fake Source (Kamat)", has_safety_period=True)

        self.add_argument("--source-period", type=float, required=True)
        self.add_argument("--source-mobility",
                          type=simulator.MobilityModel.eval_input,
                          default=simulator.MobilityModel.StationaryMobilityModel())

        self.add_argument("--pr-fake", type=restricted_float, required=True)
        self.add_argument("--fake-send-delay", type=float, default=50)

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result.update({
            "FAKE_PROBABILITY": str(self.args.pr_fake),
            "FAKE_SEND_DELAY_MS": str(self.args.fake_send_delay)
        })

        return result
