import argparse
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.SourcePeriodModel
import simulator.MobilityModel

class Arguments(ArgumentsCommon):
    def __init__(self):
        parser = argparse.ArgumentParser(description="Protectionless TDMA DAS", add_help=True)
        super(Arguments, self).__init__(parser, has_safety_period=False)

        parser.add_argument("--source-period",
            type=simulator.SourcePeriodModel.eval_input, required=True)
        parser.add_argument("-sp", "--slot-period", type=float, required=True, help="Time of a single slot")
        parser.add_argument("-dp", "--dissem-period", type=float, required=True, help="Time of the beaconing period")
        parser.add_argument("-ts", "--tdma-num-slots", type=int, required=True, help="Total number of slots available")
        parser.add_argument("-ai", "--slot-assignment-interval", type=int, required=True, help="The interval at which slot values are assigned")
        parser.add_argument("-msp", "--minimum-setup-periods", type=int, required=False, default=0, help="Minimum number of periods required for setup")
        parser.add_argument("-pbp", "--pre-beaconing-periods", type=int, required=False, default=3, help="Number of periods of neighbour discovery")
        parser.add_argument("-dt", "--dissem-timeout", type=int, required=False, default=5, help="Timeout to stop sending dissem messages")
        parser.add_argument("--source-mobility",
            type=simulator.MobilityModel.eval_input,
            default=simulator.MobilityModel.StationaryMobilityModel())

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result["SLOT_PERIOD_MS"] = int(self.args.slot_period * 1000)
        result["DISSEM_PERIOD_MS"] = int(self.args.dissem_period * 1000)
        result["TDMA_NUM_SLOTS"] = self.args.tdma_num_slots
        result["SLOT_ASSIGNMENT_INTERVAL"] = self.args.slot_assignment_interval
        result["TDMA_SETUP_PERIODS"] = self.args.minimum_setup_periods
        result["TDMA_PRE_BEACON_PERIODS"] = self.args.pre_beaconing_periods
        result["TDMA_DISSEM_TIMEOUT"] = self.args.dissem_timeout

        return result
