import multiprocessing

from simulator.Simulator import Simulator
import simulator.Attacker as Attacker
import simulator.Configuration as Configuration

class ArgumentsCommon(object):
    def __init__(self, parser, has_safety_period=False):
        parser.add_argument("--mode", type=str, choices=["GUI", "PARALLEL", "CLUSTER"], required=True)

        parser.add_argument("--seed", type=int)

        parser.add_argument("-cm", "--communication-model", type=str, choices=Simulator.available_communication_models(), required=True)
        parser.add_argument("-nm", "--noise-model", type=str, choices=Simulator.available_noise_models(), required=True)

        parser.add_argument("-ns", "--network-size", type=int, required=True)
        parser.add_argument("-d", "--distance", type=float, default=4.5)
        parser.add_argument("-c", "--configuration", type=str, required=True, choices=Configuration.names())

        parser.add_argument("-am", "--attacker-model", type=Attacker.eval_input, default=Attacker.default())

        if has_safety_period:
            parser.add_argument("-safety", "--safety-period", type=float, required=True)

        parser.add_argument("--job-size", type=int, default=1)
        parser.add_argument("--thread-count", type=int, default=multiprocessing.cpu_count())

        parser.add_argument("-v", "--verbose", action="store_true")

        self.parser = parser

        # Haven't parsed anything yet
        self.args = None

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
        else:
            configuration = Configuration.create(self.args.configuration, self.args)

            if len(configuration.source_ids) != 1:
                raise RuntimeError("Invalid number of source ids in configuration {}, there must be exactly one.".format(configuration))

            (source_id,) = configuration.source_ids

            result["SOURCE_NODE_ID"] = source_id

        return result
