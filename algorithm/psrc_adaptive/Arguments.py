from data.restricted_eval import restricted_eval

import argparse, multiprocessing, ast
import simulator.Configuration as Configuration
import simulator.Attacker as Attacker
import simulator.SourcePeriodModel

approaches = [ "PB_SINK_APPROACH", "PB_ATTACKER_EST_APPROACH" ]

def source_period_model(source):
    return restricted_eval(source, simulator.SourcePeriodModel.models())

class Arguments:
    def __init__(self):
        parser = argparse.ArgumentParser(description="SLP Adaptive", add_help=True)
        parser.add_argument("--mode", type=str, choices=["GUI", "PARALLEL", "CLUSTER"], required=True)

        parser.add_argument("--seed", type=int)

        parser.add_argument("--network-size", type=int, required=True)
        parser.add_argument("--safety-period", type=float, required=True)

        parser.add_argument("--source-period", type=source_period_model, required=True)

        parser.add_argument("--approach", type=str, choices=approaches, required=True)

        parser.add_argument("--distance", type=float, required=True)

        parser.add_argument("--configuration", type=str, required=True, choices=Configuration.Names())

        parser.add_argument("--attacker-model", type=str, choices=Attacker.models(), default=Attacker.default())

        parser.add_argument("--job-size", type=int, default=1)
        parser.add_argument("--thread-count", type=int, default=multiprocessing.cpu_count())

        parser.add_argument("-v", "--verbose", action="store_true")

        self.parser = parser

    def parse(self, argv):
        self.args = self.parser.parse_args(argv)
        return self.args

    def build_arguments(self):
        result = {}

        if self.args.verbose:
            result["SLP_VERBOSE_DEBUG"] = 1

        result.update({
            "APPROACH": self.args.approach,
            self.args.approach: 1,
        })

        result.update(self.args.source_period.build_arguments())

        return result
