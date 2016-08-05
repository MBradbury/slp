from __future__ import print_function

import itertools

from simulator.Simulation import Simulation
from simulator import CommandLineCommon

from data import results, latex
from data.table import safety_period, direct_comparison, fake_result
from data.graph import summary, versus

from data.run.common import RunSimulationsCommon as RunSimulations

class CLI(CommandLineCommon.CLI):

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

    local_parameter_names = tuple()

    def __init__(self):
        super(CLI, self).__init__(__package__)

    def _argument_product(self):
        argument_product = list(itertools.product(
            self.sizes, self.configurations,
            self.attacker_models, self.noise_models, self.communication_models,
            [self.distance], self.source_periods
        ))

        return argument_product

    def _execute_runner(self, driver, result_path, skip_completed_simulations=True):
        runner = RunSimulations(driver, self.algorithm_module, result_path,
                                skip_completed_simulations=skip_completed_simulations)

        runner.run(self.repeats, self.parameter_names(), self._argument_product())

    def _run_table(self, args):
        noforward_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=('normal latency', 'ssd', 'captured', 'fake', 'received ratio'))

        result_table = fake_result.ResultTable(noforward_results)

        self._create_table(self.algorithm_module.name + "-results", result_table)

    def run(self, args):
        super(CLI, self).run(args)

        if 'table' in args:
            self._run_table(args)
