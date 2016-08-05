import argparse
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.SourcePeriodModel
import simulator.MobilityModel
import simulator.Configuration as Configuration

class Arguments(ArgumentsCommon):
    def __init__(self):
        parser = argparse.ArgumentParser(description="SLP Phantom GROW", add_help=True)
        super(Arguments, self).__init__(parser, has_safety_period=True)

        parser.add_argument("--source-period",
            type=simulator.SourcePeriodModel.eval_input, required=True)
        parser.add_argument("--source-mobility",
            type=simulator.MobilityModel.eval_input,
            default=simulator.MobilityModel.StationaryMobilityModel())

        parser.add_argument("--walk-length", type=int, required=True)

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result["RANDOM_WALK_HOPS"] = int(self.args.walk_length)

        configuration = Configuration.create(self.args.configuration, self.args)
        result["LANDMARK_NODE_ID"] = configuration.sink_id

        return result
