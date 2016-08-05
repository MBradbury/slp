from __future__ import print_function

import itertools

from simulator import CommandLineCommon

from data.table import safety_period

from data.run.common import RunSimulationsCommon as RunSimulations

class CLI(CommandLineCommon.CLI):

    local_parameter_names = ('slot period', 'dissem period', 'tdma num slots', 'slot assignment interval', 'minimum setup periods', 'pre beacon periods', "dissem timeout")

    def __init__(self):
        super(CLI, self).__init__(__package__)

    def _argument_product(self):
        parameters = self.algorithm_module.Parameters

        argument_product = list(itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models, parameters.communication_models,
            [parameters.distance], parameters.source_periods, parameters.slot_period, parameters.dissem_period,
            parameters.tdma_num_slots, parameters.slot_assignment_interval, parameters.minimum_setup_periods, parameters.dissem_timeout
        ))

        return argument_product

    def _execute_runner(self, driver, result_path, skip_completed_simulations=True):
        runner = RunSimulations(
            driver, self.algorithm_module, result_path,
            skip_completed_simulations=skip_completed_simulations
        )

        runner.run(self.algorithm_module.Parameters.repeats, self.parameter_names(), self._argument_product())

    def run(self, args):
        super(CLI, self).run(args)
