import argparse
from algorithm.common.ArgumentsCommon import ArgumentsCommon
import simulator.SourcePeriodModel
import simulator.MobilityModel

approaches = ["PB_AWAY_SRC_APPROACH"]

class Arguments(ArgumentsCommon):
    def __init__(self):
        parser = argparse.ArgumentParser(description="SLP Adaptive", add_help=True)
        super(Arguments, self).__init__(parser, has_safety_period=True)

        parser.add_argument("--source-period", type=float, required=True)
        parser.add_argument("--source-mobility",
            type=simulator.MobilityModel.eval_input,
            default=simulator.MobilityModel.StationaryMobilityModel())

        parser.add_argument("--approach", type=str, choices=approaches, required=True)

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        if self.args.verbose:
            result["SLP_VERBOSE_DEBUG"] = 1

        result.update({
            "APPROACH": self.args.approach,
            self.args.approach: 1,
        })

        return result
