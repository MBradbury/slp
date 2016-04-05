import argparse
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.SourcePeriodModel
import simulator.MobilityModel

class Arguments(ArgumentsCommon):
    def __init__(self):
        parser = argparse.ArgumentParser(description="SLP Protectionless Aggregation", add_help=True)
        super(Arguments, self).__init__(parser, has_safety_period=False)

        parser.add_argument("--source-period",
            type=simulator.SourcePeriodModel.eval_input, required=True)
        parser.add_argument("--source-mobility",
            type=simulator.MobilityModel.eval_input,
            default=simulator.MobilityModel.StationaryMobilityModel())

        parser.add_argument("--aggregation-period", type=float, required=True)

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result["AGGREGATION_PERIOD_MS"] = int(self.args.aggregation_period * 1000)

        return result
