from __future__ import print_function, division

import datetime
import itertools
import math
import os

import numpy as np

from simulator import CommandLineCommon
from simulator import Configuration

import algorithm.protectionless as protectionless

from data import results

from data.table import safety_period, fake_result
from data.graph import summary, versus
from data.util import scalar_extractor

from data.run.common import RunSimulationsCommon

class RunSimulations(RunSimulationsCommon):

    def _get_safety_period(self, argument_names, arguments):
        time_taken = super(RunSimulations, self)._get_safety_period(argument_names, arguments)

        if time_taken is None:
            return None

        return 1.3 * time_taken

class CLI(CommandLineCommon.CLI):

    local_parameter_names = ('direction bias',
                             'order', 'short count', 'long count', 'wait before short')
    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless.result_file_path, RunSimulations)

        subparser = self._subparsers.add_parser("table")
        subparser = self._subparsers.add_parser("graph")
        subparser = self._subparsers.add_parser("average-graph")
        subparser = self._subparsers.add_parser("scatter-graph")
        subparser = self._subparsers.add_parser("best-worst-average-graph")

    def _time_estimater(self, *args):
        """Estimates how long simulations are run for. Override this in algorithm
        specific CommandLine if these values are too small or too big. In general
        these have been good amounts of time to run simulations for. You might want
        to adjust the number of repeats to get the simulation time in this range."""
        names = self.parameter_names()
        size = args[names.index('network size')]
        if size == 11:
            return datetime.timedelta(hours=1)
        elif size == 15:
            return datetime.timedelta(hours=1)
        elif size == 21:
            return datetime.timedelta(hours=1)
        elif size == 25:
            return datetime.timedelta(hours=1)
        else:
            raise RuntimeError("No time estimate for network sizes other than 11, 15, 21 or 25")

    def _argument_product(self):
        parameters = self.algorithm_module.Parameters

        argument_product = itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models, parameters.communication_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.source_periods, parameters.direction_biases, parameters.orders,
            parameters.short_counts, parameters.long_counts, parameters.wait_before_short
        )

        argument_product = [
            (s, c, am, nm, cm, d, nido, lnst, sp, db, o, sc, lc, wbs)

            for (s, c, am, nm, cm, d, nido, lnst, sp, db, o, sc, lc, wbs) in argument_product

        ]        

        argument_product = self.adjust_source_period_for_multi_source(argument_product)

        return argument_product

    def _run_table(self, args):
        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=('normal latency', 'ssd', 'captured', 'sent', 'received ratio'))

        result_table = fake_result.ResultTable(phantom_results)

        self._create_table("{}-results".format(self.algorithm_module.name), result_table)

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (seconds)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
        }

        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            source_period_normalisation="NumSources"
        )

        parameters = [
            ('source period', ' seconds')
        ]

        custom_yaxis_range_max = {
            'captured': 50,
            'sent': 30000
        }

        for (parameter_name, parameter_unit) in parameters:
            for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                name = '{}-v-{}'.format(yaxis.replace(" ", "_"), parameter_name.replace(" ", "-"))

                g = versus.Grapher(
                    self.algorithm_module.graphs_path, name,
                    xaxis='network size', yaxis=yaxis, vary=parameter_name,
                    yextractor=scalar_extractor
                )

                g.xaxis_label = 'Network Size'
                g.yaxis_label = yaxis_label
                g.vary_label = parameter_name.title()
                g.vary_prefix = parameter_unit
                g.key_position = key_position

                if yaxis in custom_yaxis_range_max:
                    g.yaxis_range_max = custom_yaxis_range_max[yaxis]

                g.create(phantom_results)

                summary.GraphSummary(
                    os.path.join(self.algorithm_module.graphs_path, name),
                    self.algorithm_module.name + '-' + name
                ).run()

    def run(self, args):
        args = super(CLI, self).run(args)

        if 'table' == args.mode:
            self._run_table(args)

        if 'graph' == args.mode:
            self._run_graph(args)
