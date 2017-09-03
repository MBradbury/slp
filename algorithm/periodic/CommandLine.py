from __future__ import print_function

import itertools

from simulator import CommandLineCommon

import algorithm
protectionless = algorithm.import_algorithm("protectionless")

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless.result_file_path)

    def _argument_product(self, extras=None):
        parameters = self.algorithm_module.Parameters

        argument_product = itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models,
            parameters.communication_models, parameters.fault_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.periods
        )

        argument_product = [
            (size, config, attacker, noise, communication_model, fm, distance, nido, lnst, src_period, broadcast_period)
            for (size, config, attacker, noise, communication_model, fm, distance, nido, lnst, (src_period, broadcast_period))
            in argument_product
        ]

        argument_product = self.add_extra_arguments(argument_product, extras)

        return argument_product

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 2.0
