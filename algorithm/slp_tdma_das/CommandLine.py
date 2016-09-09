from __future__ import print_function

import itertools

from simulator import CommandLineCommon

#import algorithm.protectionless_tdma_das as protectionless_tdma_das

from data.run.common import RunSimulationsCommon
from data.table import safety_period

class RunSimulations(RunSimulationsCommon):
    def _get_safety_period(self, argument_names, arguments):
        minimum_setup_period = arguments[argument_names.index("minimum setup periods")]
        tdma_safety_period = arguments[argument_names.index("tdma safety periods")]

        period_length_sec = 3

        return (minimum_setup_period + tdma_safety_period) * period_length_sec

class CLI(CommandLineCommon.CLI):

    local_parameter_names = ('slot period', 'dissem period', 'tdma num slots', 'slot assignment interval',
                             'minimum setup periods', 'pre beacon periods', 'dissem timeout',
                             'search distance', 'tdma safety periods')

    def __init__(self):
        super(CLI, self).__init__(__package__, True, RunSimulations)

    def _argument_product(self):
        parameters = self.algorithm_module.Parameters

        argument_product = list(itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models, parameters.communication_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.source_periods, parameters.slot_periods, parameters.dissem_periods,
            parameters.tdma_num_slots, parameters.slot_assignment_intervals, parameters.minimum_setup_periods,
            parameters.pre_beacon_periods, parameters.dissem_timeouts, parameters.tdma_safety_periods_and_search_distances
        ))

        argument_product = [
            (s, c, am, nm, cm, d, nido, lnst, src_period, sp, dp, ts, ai, msp, pbp, dt, tsp, sd)
            for (s, c, am, nm, cm, d, nido, lnst, src_period, sp, dp, ts, ai, msp, pbp, dt, (tsp, sd))
            in argument_product
        ]

        argument_product = self.adjust_source_period_for_multi_source(argument_product)

        return argument_product


    def run(self, args):
        args = super(CLI, self).run(args)
