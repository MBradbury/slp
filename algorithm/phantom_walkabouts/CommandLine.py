from __future__ import print_function, division

import datetime
import itertools
import math
import os.path

import numpy as np

from simulator import CommandLineCommon
from simulator import Configuration

import algorithm

#import algorithm.protectionless as protectionless
import algorithm
protectionless = algorithm.import_algorithm("protectionless")
phantom_chen = algorithm.import_algorithm("phantom_chen")

from data import results

from data.table import safety_period, fake_result
from data.graph import summary, versus, min_max_versus
from data.util import scalar_extractor

from data.run.common import RunSimulationsCommon

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless.result_file_path)

        subparser = self._add_argument("table", self._run_table)
        subparser = self._add_argument("graph", self._run_graph)
        subparser = self._add_argument("graph-min-max", self._run_min_max_versus)
        subparser = self._add_argument("graph-multi", self._run_multi_versus)

    def _cluster_time_estimator(self, args, **kwargs):
        """Estimates how long simulations are run for. Override this in algorithm
        specific CommandLine if these values are too small or too big. In general
        these have been good amounts of time to run simulations for. You might want
        to adjust the number of repeats to get the simulation time in this range."""
        size = args['network size']
        if size == 11:
            return datetime.timedelta(hours=2)
        elif size == 15:
            return datetime.timedelta(hours=2)
        elif size == 21:
            return datetime.timedelta(hours=2)
        elif size == 25:
            return datetime.timedelta(hours=2)
        else:
            raise RuntimeError("No time estimate for network sizes other than 11, 15, 21 or 25")

    def _argument_product(self):
        parameters = self.algorithm_module.Parameters

        argument_product = itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models,
            parameters.communication_models, parameters.fault_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.source_periods,
            parameters.safety_factors,
            parameters.direction_bias, parameters.orders,
            parameters.short_counts, parameters.long_counts, parameters.wait_before_short
        )

        argument_product = [
            (s, c, am, nm, cm, fm, d, nido, lnst, sp, sf, db, o, sc, lc, wbs)

            for (s, c, am, nm, cm, fm, d, nido, lnst, sp, sf, db, o, sc, lc, wbs) in argument_product

        ]        

        argument_product = self.adjust_source_period_for_multi_source(argument_product)

        return argument_product

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 1.0

    def _run_table(self, args):
        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=('normal latency', 'ssd', 'captured', 'sent', 'received ratio'))

        result_table = fake_result.ResultTable(phantom_results)

        self._create_table("{}-results".format(self.algorithm_module.name), result_table)

    @staticmethod
    def vvalue_converter(name):
        try:
            (bias, order, short_count, long_count, wait) = name

            if short_count == 1 and long_count == 0:
                return "1, 0"
            elif short_count == 1 and long_count == 1:
                return "1, 1"
            elif short_count == 1 and long_count == 2:
                return "1, 2"
            else:
                return name
        except ValueError:
            return name

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left bottom'),
            'captured': ('Capture Ratio (%)', 'left top'),
            #'sent': ('Total Messages Sent', 'left top'),
            'norm(sent,time taken)': ('Messages Sent per Second', 'left bottom'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'utility equal': ('Utility (Equal)', 'left top'),
            'utility animal': ('Utility (Habitat)', 'left top'),
            'utility battle': ('Utility (Military)', 'left top'),
        }

        varying = [
            (('network size', ''), (('direction bias', 'order', 'short count', 'long count', 'wait before short'), '')),
            (('safety factor', ''), (('direction bias', 'order', 'short count', 'long count', 'wait before short'), '')),
        ]

        custom_yaxis_range_max = {
            'received ratio': 100,
        }

        def filter_params(all_params):
            return all_params['safety factor'] != '1.4'


        self._create_versus_graph(graph_parameters, varying, custom_yaxis_range_max,
            source_period_normalisation="NumSources",
            results_filter=filter_params,
            vary_label='PW',
            vvalue_label_converter=self.vvalue_converter,
        )

    def _run_min_max_versus(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (milliseconds)', 'left bottom'),
            'captured': ('Capture Ratio (%)', 'left top'),
            'norm(sent,time taken)': ('Messages Transmission (messages)', 'left bottom'),
            'received ratio': ('Delivery Ratio (%)', 'left bottom'),
            'utility equal': ('Utility (Equal)', 'right top'),
            'utility animal': ('Utility (Habitat)', 'right top'),
            'utility battle': ('Utility (Military)', 'right top'),
        }

        varying = [
            (('safety factor', ''), (('direction bias', 'order', 'short count', 'long count', 'wait before short'), '')),
        ]
        
        custom_yaxis_range_max = {
            #'normal latency': 500,
            #'norm(sent,time taken)': 600,
            'received ratio': 100,
            'capture ratio': 100,
            'utility equal': 0.8,
            'utility animal': 0.8,
            'utility battle': 0.8,
        }

        self._create_min_max_versus_graph(
            [phantom_chen], None, graph_parameters, varying, custom_yaxis_range_max,
            min_label=["Phantom - Min"],
            max_label=["Phantom - Max"],
            min_max_same_label=["Phantom"],
            vary_label="",
            comparison_label="PW",
            vvalue_label_converter=self.vvalue_converter,
        )

    def _run_multi_versus(self, args):
        graph_parameters = [
            ('utility equal', 'Utility (Equal)'),
            ('utility animal', 'Utility (Animal)'),
            ('utility battle', 'Utility (Battle)'),
        ]

        varying = [
            ('safety factor', ''),
        ]
        
        custom_yaxis_range_max = 1.0

        self._create_multi_versus_graph(
            graph_parameters, varying, "Utility (\\%)", custom_yaxis_range_max
        )
