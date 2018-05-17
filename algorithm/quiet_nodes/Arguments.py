
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.SourcePeriodModel
import simulator.MobilityModel

class Arguments(ArgumentsCommon):
    def __init__(self):
        super(Arguments, self).__init__("SLP Quiet Nodes", has_safety_period=True, has_safety_factor=True)

        self.add_argument("--source-period",
                          type=simulator.SourcePeriodModel.eval_input, required=True)
        self.add_argument("--source-mobility",
                          type=simulator.MobilityModel.eval_input,
                          default=simulator.MobilityModel.StationaryMobilityModel())

        self.add_argument("--quiet-node-distance", type=self.type_positive_int, required=True)

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result["QUIET_NODE_DISTANCE"] = self.args.quiet_node_distance

        return result
