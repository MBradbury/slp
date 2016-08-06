from __future__ import print_function

import itertools

from simulator import CommandLineCommon

import algorithm.protectionless as protectionless

from data.table import safety_period

class CLI(CommandLineCommon.CLI):

    local_parameter_names = ('broadcast period',)

    def __init__(self):
        super(CLI, self).__init__(__package__)

    def _argument_product(self):
        parameters = self.algorithm_module.Parameters

        argument_product = itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models, parameters.communication_models,
            [parameters.distance], parameters.periods
        )

        argument_product = [
            (size, config, attacker, noise, communication_model, distance, src_period, broadcast_period)
            for (size, config, attacker, noise, communication_model, distance, (src_period, broadcast_period))
            in argument_product
        ]

        return argument_product

    def _execute_runner(self, driver, result_path, skip_completed_simulations=True):
        if driver.mode() == "TESTBED":
            from data.run.common import RunTestbedCommon as RunSimulations
        else:
            from data.run.common import RunSimulationsCommon as RunSimulations

        safety_period_table_generator = safety_period.TableGenerator(protectionless.result_file_path)
        safety_periods = safety_period_table_generator.safety_periods()

        runner = RunSimulations(
            driver, self.algorithm_module, result_path,
            skip_completed_simulations=skip_completed_simulations,
            safety_periods=safety_periods
        )

        runner.run(self.algorithm_module.Parameters.repeats, self.parameter_names(), self._argument_product())

    def run(self, args):
        super(CLI, self).run(args)
