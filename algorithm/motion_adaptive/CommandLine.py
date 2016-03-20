from __future__ import print_function

import itertools

from simulator import CommandLineCommon

import algorithm.protectionless as protectionless

from data import results
from data.table import safety_period

from data.run.common import RunSimulationsCommon as RunSimulations

class CLI(CommandLineCommon.CLI):

    executable_path = 'run.py'

    distance = 4.5

    noise_models = ["meyer-heavy"]

    communication_models = ["low-asymmetry"]

    sizes = [11, 15, 21, 25]

    source_periods = [1.0, 0.5, 0.25, 0.125]

    configurations = [
        ('SourceCorner', 'CHOOSE'),
        #('SinkCorner', 'CHOOSE'),
        #('FurtherSinkCorner', 'CHOOSE'),
        #('Generic1', 'CHOOSE'),
        #('Generic2', 'CHOOSE'),

        #('RingTop', 'CHOOSE'),
        #('RingOpposite', 'CHOOSE'),
        #('RingMiddle', 'CHOOSE'),

        #('CircleEdges', 'CHOOSE'),
        #('CircleSourceCentre', 'CHOOSE'),
        #('CircleSinkCentre', 'CHOOSE'),
    ]

    attacker_models = ['SeqNoReactiveAttacker()']

    pull_back_approaches = ["PB_SINK_APPROACH", "PB_ATTACKER_EST_APPROACH"]
    pfs_move_approaches = ['PFS_MOVE_RANDOM', 'PFS_MOVE_MIRROR']

    repeats = 300

    local_parameter_names = ('pull_back_approach', 'move_approach')

    protectionless_configurations = [name for (name, build) in configurations]
    

    def __init__(self):
        super(CLI, self).__init__(__package__)

    def _execute_runner(self, driver, result_path, skip_completed_simulations):
        safety_period_table_generator = safety_period.TableGenerator(protectionless.result_file_path)
        safety_periods = safety_period_table_generator.safety_periods()

        runner = RunSimulations(
            driver, self.algorithm_module, result_path,
            skip_completed_simulations=skip_completed_simulations,
            safety_periods=safety_periods
        )

        argument_product = list(itertools.product(
            self.sizes, self.protectionless_configurations,
            self.attacker_models, self.noise_models, self.communication_models,
            [self.distance], self.source_periods,
            self.pull_back_approaches, self.pfs_move_approaches
        ))

        runner.run(self.executable_path, self.repeats, self.parameter_names(), argument_product)

    def run(self, args):
        super(CLI, self).run(args)
