
from __future__ import division

from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.Configuration
import simulator.SourcePeriodModel
import simulator.MobilityModel

class Arguments(ArgumentsCommon):
    def __init__(self):
        super(Arguments, self).__init__("SLP TDMA DAS", has_safety_period=True)

        self.add_argument("--source-period",
                          type=simulator.SourcePeriodModel.eval_input, required=True)
        self.add_argument("-sp", "--slot-period", type=float, required=True, help="Time of a single slot")
        self.add_argument("-dp", "--dissem-period", type=float, required=True, help="Time of the beacon period")
        self.add_argument("-ts", "--tdma-num-slots", type=int, required=True, help="Total number of slots available")
        self.add_argument("-ai", "--slot-assignment-interval", type=int, required=True, help="The interval at which slot values are assigned")
        self.add_argument("-msp", "--minimum-setup-periods", type=int, required=True, help="Minimum number of periods required for setup")
        self.add_argument("-pbp", "--pre-beacon-periods", type=int, required=False, default=3, help="Number of periods of neighbour discovery")
        self.add_argument("-dt", "--dissem-timeout", type=int, required=False, default=5, help="Timeout to stop sending dissem messages")
        # self.add_argument("-tsp", "--tdma-safety-periods", type=int, required=True, help="Safety period (in TDMA periods)")
        self.add_argument("-sd", "--search-distance", type=int, required=True, help="Distance search messages travel from the sink")
        self.add_argument("--simulate-crash", type=int, required=False, default=0, help="Simulate a node crash with the NodeCrashVariableFaultModel(variable_name=SourceBroadcasterC.simulate_crash,variable_value=True) fault model")
        self.add_argument("--source-mobility",
                          type=simulator.MobilityModel.eval_input,
                          default=simulator.MobilityModel.StationaryMobilityModel())

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        configuration = simulator.Configuration.create(self.args.configuration, self.args)

        if len(configuration.source_ids) != 1:
            raise RuntimeError("Configuration must have one and only one source")

        (source_id,) = configuration.source_ids

        ssd_hops = configuration.ssd(source_id)

        result["SLOT_PERIOD_MS"] = int(self.args.slot_period * 1000)
        result["DISSEM_PERIOD_MS"] = int(self.args.dissem_period * 1000)
        result["TDMA_NUM_SLOTS"] = self.args.tdma_num_slots
        result["SLOT_ASSIGNMENT_INTERVAL"] = self.args.slot_assignment_interval
        result["TDMA_SETUP_PERIODS"] = self.args.minimum_setup_periods
        result["TDMA_PRE_BEACON_PERIODS"] = self.args.pre_beacon_periods
        result["TDMA_DISSEM_TIMEOUT"] = self.args.dissem_timeout
        # result["SAFETY_PERIOD"] = ssd_hops
        result["SEARCH_DIST"] = self.args.search_distance
        result["CHANGE_LENGTH"] = ssd_hops - self.args.search_distance
        result["SIMULATED_CRASH"] = self.args.simulate_crash

        return result
