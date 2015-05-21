import argparse
from algorithm.common.ArgumentsCommon import ArgumentsCommon
import simulator.SourcePeriodModel
import simulator.MobilityModel

class Arguments(ArgumentsCommon):
    def __init__(self):
        parser = argparse.ArgumentParser(description="SLP Phantom Reliable", add_help=True)
        super(Arguments, self).__init__(parser, has_safety_period=True)

        parser.add_argument("--safety-period", type=float, required=True)

        parser.add_argument("--source-period",
            type=simulator.SourcePeriodModel.eval_input, required=True)
        parser.add_argument("--source-mobility",
            type=simulator.MobilityModel.eval_input,
            default=simulator.MobilityModel.StationaryMobilityModel())

        parser.add_argument("--random-walk-hops", type=int, required=True)
        parser.add_argument("--random-walk-retries", type=int, required=True)

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result["RANDOM_WALK_HOPS"] = int(self.args.random_walk_hops)
        result["RANDOM_WALK_RETRIES"] = int(self.args.random_walk_retries)

        return result
