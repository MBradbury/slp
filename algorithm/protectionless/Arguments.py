import argparse, multiprocessing
import simulator.Configuration as Configuration
import simulator.Attacker as Attacker
import simulator.SourcePeriodModel
import simulator.MobilityModel

class Arguments:
    def __init__(self):
        parser = argparse.ArgumentParser(description="SLP Protectionless", add_help=True)
        parser.add_argument("--mode", type=str, choices=["GUI", "PARALLEL", "CLUSTER"], required=True)

        parser.add_argument("--seed", type=int)

        parser.add_argument("--network-size", type=int, required=True)

        parser.add_argument("--source-period",
            type=simulator.SourcePeriodModel.eval_input, required=True)
        parser.add_argument("--source-mobility",
            type=simulator.MobilityModel.eval_input,
            default=simulator.MobilityModel.StationaryMobilityModel())

        parser.add_argument("--distance", type=float, default=4.5)

        parser.add_argument("--configuration", type=str, required=True, choices=Configuration.names())

        parser.add_argument("--attacker-model", type=str, choices=Attacker.models(), default=Attacker.default())

        parser.add_argument("--job-size", type=int, default=1)
        parser.add_argument("--thread-count", type=int, default=multiprocessing.cpu_count())

        parser.add_argument("-v", "--verbose", action="store_true")

        self.parser = parser

    def parse(self, argv):
        self.args = self.parser.parse_args(argv)

        configuration = Configuration.create(self.args.configuration, self.args)
        self.args.source_mobility.setup(configuration)

        return self.args

    def build_arguments(self):
        result = {}

        if self.args.verbose:
            result["SLP_VERBOSE_DEBUG"] = 1

        result.update(self.args.source_period.build_arguments())
        result.update(self.args.source_mobility.build_arguments())

        return result
