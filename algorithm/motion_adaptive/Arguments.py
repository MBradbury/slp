import argparse
from simulator.ArgumentsCommon import ArgumentsCommon
import simulator.SourcePeriodModel
import simulator.MobilityModel

pb_approaches = [ "PB_SINK_APPROACH", "PB_ATTACKER_EST_APPROACH" ]
move_approaches = [ "PFS_MOVE_RANDOM", "PFS_MOVE_MIRROR" ]

class Arguments(ArgumentsCommon):
    def __init__(self):
        parser = argparse.ArgumentParser(description="SLP Adaptive", add_help=True)
        super(Arguments, self).__init__(parser, has_safety_period=True)

        parser.add_argument("--source-period",
            type=simulator.SourcePeriodModel.eval_input, required=True)
        parser.add_argument("--source-mobility",
            type=simulator.MobilityModel.eval_input,
            default=simulator.MobilityModel.StationaryMobilityModel())

        parser.add_argument("--pull-back-approach", type=str, choices=pb_approaches, required=True)
        parser.add_argument("--pfs-move-approach", type=str, choices=move_approaches, required=True)

    def build_arguments(self):
        result = super(Arguments, self).build_arguments()

        result.update({
            "PULL_BACK_APPROACH": self.args.pull_back_approach,
            self.args.pull_back_approach: 1,

            "PFS_MOVE_APPROACH": self.args.pfs_move_approach,
            self.args.pfs_move_approach: 1,
        })

        return result
