
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.Configuration
import simulator.SourcePeriodModel
import simulator.MobilityModel

class Arguments(ArgumentsCommon):
    def __init__(self):
        super(Arguments, self).__init__("SLP TDMA DAS Crash Tolerant", has_safety_period=True)

        self.add_argument("--source-period",
                          type=simulator.SourcePeriodModel.eval_input, required=True)
        self.add_argument("-sp", "--slot-period", type=float, required=True, help="Time of a single slot")
        self.add_argument("-dp", "--dissem-period", type=float, required=True, help="Time of the beacon period")
        self.add_argument("-ts", "--tdma-num-slots", type=int, required=True, help="Total number of slots available")
        self.add_argument("-ai", "--slot-assignment-interval", type=int, required=True, help="The interval at which slot values are assigned")
        self.add_argument("-msp", "--minimum-setup-periods", type=int, required=True, help="Minimum number of periods required for setup")
        self.add_argument("-pbp", "--pre-beacon-periods", type=int, required=False, default=3, help="Number of periods of neighbour discovery")
        self.add_argument("-sd", "--search-distance", type=int, required=True, help="Distance search messages travel from the sink")
        self.add_argument("--timesync", choices=("enabled", "disabled"), default="disabled", required=False, help="Activate TDMA timesync")
        self.add_argument("-tsp", "--timesync-period", type=float, required=False, default=0, help="Time at the end of the TDMA period for FTSP timesync (0 turns timesync off)")
        self.add_argument("--source-mobility",
                          type=simulator.MobilityModel.eval_input,
                          default=simulator.MobilityModel.StationaryMobilityModel())

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        configuration = simulator.Configuration.create(self.args.configuration, self.args)

        if len(configuration.source_ids) != 1:
            raise RuntimeError("Configuration must have one and only one source")

        (source_id,) = configuration.source_ids
        (sink_id,) = configuration.sink_ids

        ssd_hops = configuration.ssd(sink_id, source_id)

        result["SLOT_PERIOD_MS"] = int(self.args.slot_period * 1000)
        result["DISSEM_PERIOD_MS"] = int(self.args.dissem_period * 1000)
        result["TDMA_NUM_SLOTS"] = self.args.tdma_num_slots
        result["SLOT_ASSIGNMENT_INTERVAL"] = self.args.slot_assignment_interval
        result["TDMA_SETUP_PERIODS"] = self.args.minimum_setup_periods
        result["TDMA_PRE_BEACON_PERIODS"] = self.args.pre_beacon_periods
        result["SEARCH_DIST"] = self.args.search_distance
        result["CHANGE_LENGTH"] = ssd_hops - self.args.search_distance
        result["TDMA_TIMESYNC"] = 1 if self.args.timesync == "enabled" else 0
        result["TIMESYNC_PERIOD_MS"] = int(self.args.timesync_period * 1000)

        return result
