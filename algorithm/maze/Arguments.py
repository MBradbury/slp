
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.SourcePeriodModel
import simulator.MobilityModel

approaches = ("SINK_SRC", "SRC_SINK", "SINK_SRC_SINK", "SRC_SINK_SRC")

restricted_sleep = ("ALL_SLEEP", "NO_FAR_SLEEP")

class Arguments(ArgumentsCommon):
    def __init__(self):
        super().__init__("SLP Quiet Nodes", has_safety_period=True, has_safety_factor=True)

        self.add_argument("--source-period",
                          type=simulator.SourcePeriodModel.eval_input, required=True)
        self.add_argument("--source-mobility",
                          type=simulator.MobilityModel.eval_input,
                          default=simulator.MobilityModel.StationaryMobilityModel())

        self.add_argument("--sleep-duration", type=self.type_positive_float, required=True)
        self.add_argument("--sleep-probability", type=self.type_probability, required=True)

        self.add_argument("--non-sleep-source", type=self.type_positive_int, required=True)
        self.add_argument("--non-sleep-sink", type=self.type_positive_int, required=True)

        self.add_argument("--approach", type=str, choices=approaches, required=True)
        self.add_argument("--restricted-sleep", type=str, choices=restricted_sleep, required=True)

    def build_arguments(self):
        result = super().build_arguments()

        result["SLEEP_DURATION"] = int(self.args.sleep_duration)
        result["SLEEP_PROBABILITY"] = int(self.args.sleep_probability * 100)

        result["NON_SLEEP_SOURCE"] = self.args.non_sleep_source # hops
        result["NON_SLEEP_SINK"] = self.args.non_sleep_sink # hops

        result[self.args.approach] = 1
        result[self.args.restricted_sleep] = 1

        return result
