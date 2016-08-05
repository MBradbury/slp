import argparse
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.MobilityModel

class Arguments(ArgumentsCommon):
    def __init__(self):
        parser = argparse.ArgumentParser(description="SLP Source Flood Fake", add_help=True)
        super(Arguments, self).__init__(parser, has_safety_period=True)

        parser.add_argument("--source-period", type=float, required=True)
        parser.add_argument("--source-mobility",
                            type=simulator.MobilityModel.eval_input,
                            default=simulator.MobilityModel.StationaryMobilityModel())

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()
        return result
