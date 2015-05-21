import multiprocessing

from simulator.Simulator import Simulator
import simulator.Attacker as Attacker
import simulator.Configuration as Configuration

class ArgumentsCommon(object):
    def __init__(self, parser, has_safety_period=False):
        parser.add_argument("--mode", type=str, choices=["GUI", "PARALLEL", "CLUSTER"], required=True)

        parser.add_argument("--seed", type=int)

        parser.add_argument("--noise-model", type=str, choices=Simulator.available_noise_models(), required=True)

        parser.add_argument("--network-size", type=int, required=True)
        parser.add_argument("--distance", type=float, default=4.5)
        parser.add_argument("--configuration", type=str, required=True, choices=Configuration.names())

        parser.add_argument("--attacker-model", type=Attacker.eval_input, default=Attacker.default())

        if has_safety_period:
            parser.add_argument("--safety-period", type=float, required=True)

        parser.add_argument("--job-size", type=int, default=1)
        parser.add_argument("--thread-count", type=int, default=multiprocessing.cpu_count())

        parser.add_argument("-v", "--verbose", action="store_true")

        self.parser = parser

    def parse(self, argv):
        self.args = self.parser.parse_args(argv)

        if hasattr(self.args, 'source_mobility'):
            configuration = Configuration.create(self.args.configuration, self.args)
            self.args.source_mobility.setup(configuration)
        
        return self.args

    def build_arguments(self):
        result = {}

        if self.args.verbose:
            result["SLP_VERBOSE_DEBUG"] = 1

        if hasattr(self.args, 'source_period'):
            if isinstance(self.args.source_period, float):
                result["SOURCE_PERIOD_MS"] = int(self.args.source_period * 1000)
            else:
                result.update(self.args.source_period.build_arguments())

        if hasattr(self.args, 'source_mobility'):
            result.update(self.args.source_mobility.build_arguments())

        return result