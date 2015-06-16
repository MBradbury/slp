from __future__ import print_function

import itertools

from algorithm.common import CommandLineCommon

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

    parameter_names = ('approach',)

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
            self.sizes, self.source_periods, self.protectionless_configurations,
            self.attacker_models, self.noise_models, self.communication_models, [self.distance],
            self.pull_back_approaches, self.pfs_move_approaches
        ))

        names = ('network_size', 'source_period', 'configuration',
                 'attacker_model', 'noise_model', 'communication_model', 'distance',
                 'pull_back_approach', 'pfs_move_approach')

        runner.run(self.executable_path, self.repeats, names, argument_product)

    def run(self, args):
        super(CLI, self).run(args)
