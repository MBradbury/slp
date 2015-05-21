from __future__ import print_function

import os, itertools

from algorithm.common import CommandLineCommon

import algorithm.protectionless as protectionless

from data import results, latex
from data.table import safety_period, direct_comparison
from data.graph import summary, heatmap, versus

from data.run.common import RunSimulationsCommon as RunSimulations

class CLI(CommandLineCommon.CLI):

    executable_path = 'run.py'

    distance = 4.5

    noise_model = "meyer-heavy"

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

        #('Source2Corners', 'CHOOSE'),
        #('Source4Corners', 'CHOOSE'),
        #('Source2Edges', 'CHOOSE'),
        #('Source4Edges', 'CHOOSE'),
        #('Source2Corner', 'CHOOSE')
    ]

    protectionless_configurations = [name for (name, build) in configurations]

    attacker_models = ['SeqNoReactiveAttacker()']

    approaches = ['PB_AWAY_SRC_APPROACH']

    repeats = 300

    parameter_names = ('approach',)

    def __init__(self):
        super(CLI, self).__init__(__package__)


    def _execute_runner(self, driver, skip_completed_simulations):
        safety_period_table_generator = safety_period.TableGenerator()
        safety_period_table_generator.analyse(protectionless.result_file_path)
        safety_periods = safety_period_table_generator.safety_periods()

        runner = RunSimulations(driver, self.algorithm_module,
            skip_completed_simulations=skip_completed_simulations, safety_periods=safety_periods)

        argument_product = list(itertools.product(
                self.sizes, self.source_periods, self.protectionless_configurations,
                self.attacker_models, [self.noise_model], [self.distance], self.approaches
        ))

        names = ('network_size', 'source_period', 'configuration',
            'attacker_model', 'noise_model', 'distance', 'approach')

        runner.run(self.executable_path, self.repeats, names, argument_product)

    def run(self, args):
        super(CLI, self).run(args)
