from __future__ import print_function, division

import os, itertools, math, datetime

import numpy as np

from simulator import CommandLineCommon

import algorithm.protectionless as protectionless

from simulator import Configuration

from data import results

from data.table import safety_period, fake_result
from data.graph import summary, versus
from data.util import scalar_extractor

class CLI(CommandLineCommon.CLI):
    local_parameter_names = ('landmark node',)

    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless.result_file_path)

        subparser = self._subparsers.add_parser("table")
        subparser = self._subparsers.add_parser("graph")

    def _time_estimater(self, args, **kwargs):
        """Estimates how long simulations are run for. Override this in algorithm
        specific CommandLine if these values are too small or too big. In general
        these have been good amounts of time to run simulations for. You might want
        to adjust the number of repeats to get the simulation time in this range."""
        size = args['network size']
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
                parameters.source_periods, parameters.landmark_nodes
        )

        argument_product = [
            (s, c, am, nm, cm, d, nido, lnst, sp, ln)

            for (s, c, am, nm, cm, d, nido, lnst, sp, ln) in argument_product
        ]

        argument_product = self.adjust_source_period_for_multi_source(argument_product)

        return argument_product

    def time_taken_to_safety_period(self, time_taken, first_normal_sent_time):
        return (time_taken - first_normal_sent_time) * 1.3

    def _run_table(self, args):
        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=('normal latency', 'ssd', 'captured', 'sent', 'received ratio', 'paths reached end', 'source dropped'))

        result_table = fake_result.ResultTable(phantom_results)

        self._create_table("{}-results".format(self.algorithm_module.name), result_table)

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (seconds)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'paths reached end': ('Paths Reached End (%)', 'right top'),
            'source dropped': ('Source Dropped Messages (%)', 'right top'),
        }

        custom_yaxis_range_max = {
            'source dropped': 100,
            'paths reached end': 100,
        }

        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            network_size_normalisation="UseNumNodes"
        )

        parameters = [
            ('source period', ' seconds'),
        ]

        for (parameter_name, parameter_unit) in parameters:
            for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                name = '{}-v-{}'.format(yaxis.replace(" ", "_"), parameter_name.replace(" ", "-"))

                g = versus.Grapher(
                    self.algorithm_module.graphs_path, name,
                    xaxis='network size', yaxis=yaxis, vary=parameter_name,
                    yextractor=scalar_extractor
                )

                g.xaxis_label = 'Number of Nodes'
                g.yaxis_label = yaxis_label
                g.vary_label = parameter_name.title()
                g.vary_prefix = parameter_unit
                g.key_position = key_position

                g.nokey = True

                g.generate_legend_graph = True

                g.point_size = 1.3
                g.line_width = 4
                g.yaxis_font = "',14'"
                g.xaxis_font = "',12'"

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
