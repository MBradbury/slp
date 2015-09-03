from __future__ import print_function, division

import itertools

from algorithm.common import CommandLineCommon

import algorithm.protectionless as protectionless

from data import results
from data.table import safety_period, fake_result
from data.run.common import RunSimulationsCommon as RunSimulations

class CLI(CommandLineCommon.CLI):

    executable_path = 'run.py'

    distance = 4.5

    noise_models = ["casino-lab", "meyer-heavy"]

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

    pr_fake = lambda size: 1 / size

    repeats = 300

    parameter_names = ('pr_fake',)

    protectionless_configurations = [name for (name, build) in configurations]

    def __init__(self):
        super(CLI, self).__init__(__package__)


    def _execute_runner(self, driver, result_path, skip_completed_simulations=True):
        safety_period_table_generator = safety_period.TableGenerator(protectionless.result_file_path)
        safety_periods = safety_period_table_generator.safety_periods()

        runner = RunSimulations(
            driver, self.algorithm_module, result_path,
            skip_completed_simulations=skip_completed_simulations, safety_periods=safety_periods)

        argument_product = list(itertools.product(
            self.sizes, self.source_periods, self.protectionless_configurations,
            self.attacker_models, self.noise_models, self.communication_models, [self.distance]
        ))

        argument_product = [
            (s, sp, c, am, nm, cm, d, self.pr_fake(s))
            for (s, sp, c, am, nm, cm, d)
            in argument_product
        ]

        names = ('network_size', 'source_period', 'configuration',
                 'attacker_model', 'noise_model', 'communication_model', 'distance', 'pr_fake')

        runner.run(self.executable_path, self.repeats, names, argument_product)


    def _run_table(self, args):
        selected_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.parameter_names,
            results=('normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs'))

        result_table = fake_result.ResultTable(selected_results)

        self._create_table(self.algorithm_module.name + "-results", result_table)

    def run(self, args):
        super(CLI, self).run(args)

        if 'table' in args:
            self._run_table(args)
