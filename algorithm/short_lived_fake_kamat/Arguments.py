import argparse
from algorithm.common.ArgumentsCommon import ArgumentsCommon
import simulator.MobilityModel

def restricted_float(x):
    x = float(x)
    if x < 0.0 or x > 1.0:
        raise argparse.ArgumentTypeError("{} not in range [0.0, 1.0]".format(x))
    return x

class Arguments(ArgumentsCommon):
    def __init__(self):
        parser = argparse.ArgumentParser(description="SLP Short Lived Fake Source (Kamat)", add_help=True)
        super(Arguments, self).__init__(parser, has_safety_period=True)

        parser.add_argument("--source-period", type=float, required=True)
        parser.add_argument("--source-mobility",
            type=simulator.MobilityModel.eval_input,
            default=simulator.MobilityModel.StationaryMobilityModel())

        parser.add_argument("--pr-fake", type=restricted_float, required=True)

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result.update({
            "FAKE_PROBABILITY": str(self.args.pr_fake)
        })

        return result
