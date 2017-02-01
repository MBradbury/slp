
from __future__ import division

from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.Configuration
import simulator.SourcePeriodModel
import simulator.MobilityModel

class Arguments(ArgumentsCommon):
    def __init__(self):
        super(Arguments, self).__init__("SLP TDMA DAS GA", has_safety_period=True)

        self.add_argument("--source-period",
                          type=simulator.SourcePeriodModel.eval_input, required=True)
        self.add_argument("-sp", "--slot-period", type=float, required=True, help="Time of a single slot")
        self.add_argument("-dp", "--dissem-period", type=float, required=True, help="Time of the beacon period")
        self.add_argument("-ts", "--tdma-num-slots", type=int, required=True, help="Total number of slots available")
        self.add_argument("--source-mobility",
                          type=simulator.MobilityModel.eval_input,
                          default=simulator.MobilityModel.StationaryMobilityModel())

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result["SLOT_PERIOD_MS"] = int(self.args.slot_period * 1000)
        result["DISSEM_PERIOD_MS"] = int(self.args.dissem_period * 1000)
        result["TDMA_NUM_SLOTS"] = self.args.tdma_num_slots

        return result
