import argparse, multiprocessing
import simulator.Configuration as Configuration
import simulator.Attacker as Attacker

def restricted_float(x):
    x = float(x)
    if x < 0.0 or x > 1.0:
        raise argparse.ArgumentTypeError("{} not in range [0.0, 1.0]".format(x))
    return x

def alpha(x):
    x = float(x)
    if int(x * 1000) <= 0:
        raise argparse.ArgumentTypeError("{} need to be at least 0.001".format(x))
    return x

class Arguments:
    def __init__(self):
        parser = argparse.ArgumentParser(description="SLP Adaptive", add_help=True)
        parser.add_argument("--mode", type=str, choices=["GUI", "PARALLEL", "CLUSTER"], required=True)

        parser.add_argument("--seed", type=int)

        parser.add_argument("--network-size", type=int, required=True)
        parser.add_argument("--safety-period", type=float, required=True)

        parser.add_argument("--source-period", type=float, required=True)
        parser.add_argument("--time-to-send", type=alpha, required=True)
        parser.add_argument("--receive-ratio", type=restricted_float, required=True)

        parser.add_argument("--approach", type=str, choices=["TWIDDLE_APPROACH", "INTUITION_APPROACH"], required=True)

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
            result.update(SLP_VERBOSE_DEBUG=1)

        result.update({
            "SOURCE_PERIOD_MS": int(self.args.source_period * 1000),
            "TIME_TO_SEND_MS": int(self.args.time_to_send * 1000),
            "RECEIVE_RATIO": str(self.args.receive_ratio),
            "APPROACH": self.args.approach,
            self.args.approach: 1,
        })

        return result
