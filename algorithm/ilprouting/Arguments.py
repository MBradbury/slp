
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.SourcePeriodModel
import simulator.MobilityModel

class Arguments(ArgumentsCommon):
    def __init__(self):
        super(Arguments, self).__init__("SLP ILP Routing", has_safety_period=True)

        self.add_argument("--source-period",
                          type=simulator.SourcePeriodModel.eval_input, required=True)
        self.add_argument("--source-mobility",
                          type=simulator.MobilityModel.eval_input,
                          default=simulator.MobilityModel.StationaryMobilityModel())

       	self.add_argument("--buffer-size", type=int, required=True)

    def build_arguments(self):
    	result = super(Arguments, self).build_arguments()

    	result["SLP_SEND_QUEUE_SIZE"] = self.args.buffer_size

    	return result
