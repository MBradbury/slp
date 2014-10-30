import argparse, multiprocessing
import simulator.Configuration as Configuration

def restricted_float(x):
	x = float(x)
	if x < 0.0 or x > 1.0:
		raise argparse.ArgumentTypeError("{} not in range [0.0, 1.0]".format(x))
	return x

class Arguments:
	def __init__(self):
		parser = argparse.ArgumentParser(description="SLP Protectionless", add_help=True)
		parser.add_argument("--mode", type=str, choices=["GUI", "PARALLEL"], required=True)

		parser.add_argument("--seed", type=int)

		parser.add_argument("--network-size", type=int, required=True)
		parser.add_argument("--safety-period", type=float, required=True)

		parser.add_argument("--source-period", type=float, required=True)
		parser.add_argument("--fake-period", type=float, required=True)
		parser.add_argument("--temp-fake-duration", type=float, required=True)

		parser.add_argument("--pr-tfs", type=restricted_float, required=True)
		parser.add_argument("--pr-pfs", type=restricted_float, required=True)

		parser.add_argument("--distance", type=float, required=True)

		parser.add_argument("--configuration", type=str, required=True, choices=Configuration.Names())

		parser.add_argument("--job-size", type=int, default=1)
		parser.add_argument("--thread-count", type=int, default=multiprocessing.cpu_count())

		self.parser = parser

	def parse(self, argv):
		self.args = self.parser.parse_args(argv)
		return self.args

	def getBuildArguments(self):
		return {
			"SOURCE_PERIOD_MS": int(self.args.source_period * 1000),
			"FAKE_PERIOD_MS": int(self.args.fake_period * 1000),
			"TEMP_FAKE_DURATION_MS": int(self.args.temp_fake_duration * 1000),
			"PR_TFS": self.args.pr_tfs,
			"PR_PFS": self.args.pr_pfs
		}
