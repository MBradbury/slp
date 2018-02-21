
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.SourcePeriodModel
import simulator.MobilityModel

def buffer_size(value):
    value = int(value)
    if value <= 0 or value >= 255:
        raise RuntimeError("Buffer size must be between 1 and 254 inclusive.")
    return value

class Arguments(ArgumentsCommon):
    def __init__(self):
        super(Arguments, self).__init__("SLP ILP Routing", has_safety_period=True)

        self.add_argument("--source-period",
                          type=simulator.SourcePeriodModel.eval_input, required=True)
        self.add_argument("--source-mobility",
                          type=simulator.MobilityModel.eval_input,
                          default=simulator.MobilityModel.StationaryMobilityModel())

        self.add_argument("--buffer-size", type=buffer_size, required=True)
        self.add_argument("--max-walk-length", type=self.type_positive_int, required=True)

        self.add_argument("--pr-direct-to-sink", type=self.type_probability, required=True)

        self.add_argument("--msg-group-size", type=self.type_positive_int, required=True)

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result["SLP_SEND_QUEUE_SIZE"] = self.args.buffer_size
        result["SLP_MAX_WALK_LENGTH"] = self.args.max_walk_length

        result["SLP_PR_SEND_DIRECT_TO_SINK"] = self.args.pr_direct_to_sink

        result["SLP_MESSAGE_GROUP_SIZE"] = self.args.msg_group_size

        return result
