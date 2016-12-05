from __future__ import print_function, division

import itertools

from simulator import CommandLineCommon

import algorithm

protectionless_tdma_das = algorithm.import_algorithm("protectionless_tdma_das")

from data.run.common import RunSimulationsCommon
from data.table import safety_period

class RunSimulations(RunSimulationsCommon):
    def _get_safety_period(self, darguments):
        time_taken = super(RunSimulations, self)._get_safety_period(darguments)

        # minimum_setup_period = darguments["minimum setup periods"]
        # tdma_safety_period = darguments["tdma safety periods"]
        # dissem_period = darguments["dissem period"]
        # slot_period = darguments["slot period"]
        # tdma_num_slots = darguments["tdma num slots"]

        # period_length_sec = dissem_period + (slot_period * tdma_num_slots)
        # tdma_safety_period = int(time_taken / period_length_sec) - minimum_setup_periods + 1

        # return (minimum_setup_period + tdma_safety_period) * period_length_sec
        return time_taken

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless_tdma_das.result_file_path, RunSimulations)

    def _argument_product(self):
        parameters = self.algorithm_module.Parameters

        argument_product = list(itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models, parameters.communication_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.source_periods, parameters.slot_period, parameters.dissem_period,
            parameters.tdma_num_slots, parameters.slot_assignment_interval, parameters.minimum_setup_periods,
            parameters.pre_beacon_periods, parameters.dissem_timeout, parameters.search_distance
        ))

        # argument_product = list(itertools.product(
            # parameters.sizes, parameters.configurations,
            # parameters.attacker_models, parameters.noise_models, parameters.communication_models,
            # [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            # parameters.source_periods, parameters.slot_periods, parameters.dissem_periods,
            # parameters.tdma_num_slots, parameters.slot_assignment_intervals, parameters.minimum_setup_periods,
            # parameters.pre_beacon_periods, parameters.dissem_timeouts, parameters.tdma_safety_periods_and_search_distances
        # ))

        # argument_product = [
                # (s, c, am, nm, cm, d, nido, lnst, src_period, sp, dp, ts, ai, msp, pbp, dt, sd, tsp)
            # for (s, c, am, nm, cm, d, nido, lnst, src_period, sp, dp, ts, ai, msp, pbp, dt, (tsp, sd))
            # in  argument_product
        # ]

        argument_product = self.adjust_source_period_for_multi_source(argument_product)

        return argument_product


    def run(self, args):
        args = super(CLI, self).run(args)
