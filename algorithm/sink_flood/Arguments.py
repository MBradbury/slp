
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.MobilityModel

class Arguments(ArgumentsCommon):
    def __init__(self):
        super(Arguments, self).__init__("SLP Source Flood Fake", has_safety_period=True)

        self.add_argument("--source-period", type=float, required=True)
        self.add_argument("--source-mobility",
                          type=simulator.MobilityModel.eval_input,
                          default=simulator.MobilityModel.StationaryMobilityModel())
