from __future__ import print_function

import itertools

from simulator.Simulator import Simulator
from algorithm.common import CommandLineCommon

from data import results, latex
from data.table import safety_period, direct_comparison, fake_result
from data.graph import summary, heatmap, versus

from data.run.common import RunSimulationsCommon as RunSimulations

class CLI(CommandLineCommon.CLI):

    executable_path = 'run.py'

    distance = 4.5

    noise_models = ["casino-lab", "meyer-heavy"]

    communication_models = ["ideal"]

    sizes = [11, 15, 21, 25]

    source_periods = [1.0, 0.5, 0.25, 0.125]

    configurations = [
        'SourceCorner',
        #'SinkCorner',
        #'FurtherSinkCorner',
        #'Generic1',
        #'Generic2',

        #'RingTop',
        #'RingOpposite',
        #'RingMiddle',

        #'CircleEdges',
        #'CircleSourceCentre',
        #'CircleSinkCentre',

        #'Source2Corners',
        #'Source4Corners',
        #'Source2Edges',
        #'Source4Edges',
        #'Source2Corner',

        #'LineSinkCentre',
        #'SimpleTreeSinkEnd'
    ]

    repeats = 750

    attacker_models = ['SeqNoReactiveAttacker()']

    parameter_names = tuple()

    def __init__(self):
        super(CLI, self).__init__(__package__)

    def _execute_runner(self, driver, result_path, skip_completed_simulations=True):
        runner = RunSimulations(driver, self.algorithm_module, result_path,
                                skip_completed_simulations=skip_completed_simulations)

        argument_product = list(itertools.product(
            self.sizes, self.source_periods, self.configurations,
            self.attacker_models, self.noise_models, self.communication_models, [self.distance]
        ))

        names = ('network_size', 'source_period', 'configuration',
                 'attacker_model', 'noise_model', 'communication_model', 'distance')

        runner.run(self.executable_path, self.repeats, names, argument_product)

    def _run_table(self, args):
        noforward_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.parameter_names,
            results=('normal latency', 'ssd', 'captured', 'fake', 'received ratio'))

        result_table = fake_result.ResultTable(noforward_results)

        self._create_table(self.algorithm_module.name + "-results", result_table)

    def run(self, args):
        super(CLI, self).run(args)

        if 'table' in args:
            self._run_table(args)
