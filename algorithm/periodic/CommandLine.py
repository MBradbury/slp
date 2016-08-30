from __future__ import print_function

import itertools

from simulator import CommandLineCommon

import algorithm.protectionless as protectionless

from data.table import safety_period

class CLI(CommandLineCommon.CLI):
    
    local_parameter_names = ('broadcast period',)

    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless.result_file_path)

    def _argument_product(self):
        parameters = self.algorithm_module.Parameters

        argument_product = itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models, parameters.communication_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.periods
        )

        argument_product = [
            (size, config, attacker, noise, communication_model, distance, nido, lnst, src_period, broadcast_period)
            for (size, config, attacker, noise, communication_model, distance, nido, lnst, (src_period, broadcast_period))
            in argument_product
        ]

        return argument_product

    def time_taken_to_safety_period(self, time_taken):
        return time_taken * 2.0


    def run(self, args):
        args = super(CLI, self).run(args)
