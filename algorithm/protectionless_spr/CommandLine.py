from __future__ import print_function

import os, itertools

from simulator import CommandLineCommon

from data import results, latex
from data.table import safety_period, direct_comparison
from data.graph import summary, versus

class CLI(CommandLineCommon.CLI):

    local_parameter_names = tuple()

    def __init__(self):
        super(CLI, self).__init__(__package__)

        subparser = self._subparsers.add_parser("table")

    def _argument_product(self):
        parameters = self.algorithm_module.Parameters

        argument_product = list(itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models, parameters.communication_models,
            [parameters.distance],  parameters.source_periods
        ))

        return argument_product

    def _execute_runner(self, driver, result_path, skip_completed_simulations=True):
        if driver.mode() == "TESTBED":
            from data.run.common import RunTestbedCommon as RunSimulations
        else:
            from data.run.common import RunSimulationsCommon as RunSimulations

        runner = RunSimulations(driver, self.algorithm_module, result_path,
                                skip_completed_simulations=skip_completed_simulations)

        runner.run(self.algorithm_module.Parameters.repeats, self.parameter_names(), self._argument_product())

    def _run_table(self, args):
        safety_period_table = safety_period.TableGenerator(self.algorithm_module.result_file_path)

        filename = '{}-results'.format(self.algorithm_module.name)

        self._create_table(filename, safety_period_table)

    def run(self, args):
        args = super(CLI, self).run(args)

        if 'table' == args.mode:
            self._run_table(args)
