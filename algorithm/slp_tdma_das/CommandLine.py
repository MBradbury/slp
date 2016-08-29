from __future__ import print_function

import itertools

from simulator import CommandLineCommon

import algorithm.protectionless_tdma_das as protectionless_tdma_das

from data.table import safety_period

class CLI(CommandLineCommon.CLI):

    local_parameter_names = ('slot period', 'dissem period', 'tdma num slots', 'slot assignment interval', 'minimum setup periods', 'pre beacon periods', "dissem timeout")

    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless_tdma_das.result_file_path)

    def _argument_product(self):
        parameters = self.algorithm_module.Parameters

        argument_product = list(itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models, parameters.communication_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.source_periods, parameters.slot_period, parameters.dissem_period,
            parameters.tdma_num_slots, parameters.slot_assignment_interval, parameters.minimum_setup_periods, parameters.dissem_timeout
        ))

        argument_product = self.adjust_source_period_for_multi_source(argument_product)

        return argument_product


    def run(self, args):
        args = super(CLI, self).run(args)
