
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.SourcePeriodModel
import simulator.MobilityModel

approaches = ("SINK_TO_SOURCE_WAVE", "SINK_TO_SOURCE_BACKWARDS", "SOURCE_TO_SINK_WAVE", "SOURCE_TO_SINK_BACKWARDS")

forced_sleep = ("RESTRICT", "BROAD")

class Arguments(ArgumentsCommon):
    def __init__(self):
        super(Arguments, self).__init__("SLP Quiet Nodes", has_safety_period=True, has_safety_factor=True)

        self.add_argument("--source-period",
                          type=simulator.SourcePeriodModel.eval_input, required=True)
        self.add_argument("--source-mobility",
                          type=simulator.MobilityModel.eval_input,
                          default=simulator.MobilityModel.StationaryMobilityModel())

        self.add_argument("--sleep-duration", type=self.type_positive_int, required=True)
        self.add_argument("--sleep-probability", type=self.type_positive_float, required=True)

        self.add_argument("--non-sleep-closer-to-source", type=self.type_positive_int, required=True)
        self.add_argument("--non-sleep-closer-to-sink", type=self.type_positive_int, required=True)

        self.add_argument("--approaches", type=str, choices=approaches, required=True)
        self.add_argument("--forced-sleep", type=str, choices=forced_sleep, required=True)

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result["SLEEP_DURATION"] = self.args.sleep_duration
        result["SLEEP_PROBABILITY"] = int(self.args.sleep_probability * 100)

        result["NON_SLEEP_CLOSER_TO_SOURCE"] = self.args.non_sleep_closer_to_source
        result["NON_SLEEP_CLOSER_TO_SINK"] = self.args.non_sleep_closer_to_sink

        result[self.args.approaches] = 1
        result[self.args.forced_sleep] = 1

        return result
