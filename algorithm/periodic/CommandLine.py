from __future__ import print_function

import itertools

from algorithm.common import CommandLineCommon

import algorithm.protectionless as protectionless

from data.table import safety_period

from data.run.common import RunSimulationsCommon as RunSimulations

class CLI(CommandLineCommon.CLI):

    executable_path = 'run.py'

    distance = 4.5

    noise_model = "casino-lab"

    sizes = [11, 15, 21, 25]

    source_periods = [1.0, 0.5, 0.25, 0.125]

    periods = [ (src_period, src_period) for src_period in source_periods ]

    configurations = [
        'SourceCorner',
        'SinkCorner',
        'FurtherSinkCorner',
        #'Generic1',
        #'Generic2',
        
        #'RingTop',
        #'RingOpposite',
        #'RingMiddle',

        #'CircleEdges',
        #'CircleSourceCentre',
        #'CircleSinkCentre',

        #'Source2Corners',
    ]

    attacker_models = ['SeqNoReactiveAttacker()']

    repeats = 300

    parameter_names = ('broadcast period')


    def __init__(self):
        super(CLI, self).__init__(__package__)


    def _execute_runner(self, driver, result_path, skip_completed_simulations=True):
        safety_period_table_generator = safety_period.TableGenerator()
        safety_period_table_generator.analyse(protectionless.result_file_path)
        safety_periods = safety_period_table_generator.safety_periods()

        runner = RunSimulations(
            driver, self.algorithm_module, result_path,
            skip_completed_simulations=skip_completed_simulations,
            safety_periods=safety_periods
        )

        argument_product = itertools.product(
            self.sizes, self.periods, self.configurations,
            self.attacker_models, [self.noise_model], [self.distance]
        )

        argument_product = [
            (size, src_period, config, attacker, noise, distance, broadcast_period)
            for (size, (src_period, broadcast_period), config, attacker, noise, distance)
            in argument_product
        ]

        names = ('network_size', 'source_period', 'configuration',
                 'attacker_model', 'noise_model', 'distance', 'broadcast_period')

        runner.run(self.executable_path, self.repeats, names, argument_product)

    def run(self, args):
        super(CLI, self).run(args)
