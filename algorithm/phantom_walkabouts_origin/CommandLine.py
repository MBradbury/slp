from __future__ import print_function, division

import datetime
import itertools
import math
import os

import numpy as np

from simulator import CommandLineCommon

import algorithm.protectionless as protectionless

from data import results

from data.table import safety_period, fake_result
from data.graph import summary, versus
from data.util import scalar_extractor

from data.run.common import RunSimulationsCommon

class RunSimulations(RunSimulationsCommon):
    def _get_safety_period(self, darguments):
        time_taken = super(RunSimulations, self)._get_safety_period(darguments)

        if time_taken is None:
            return None

        return 1.3 * time_taken

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__, protectionless.result_file_path, RunSimulations)

        subparser = self._subparsers.add_parser("table")
        subparser = self._subparsers.add_parser("graph")
        subparser = self._subparsers.add_parser("average-graph")
        subparser = self._subparsers.add_parser("scatter-graph")
        subparser = self._subparsers.add_parser("best-worst-average-graph")

    def _short_long_walk_lengths(self, s, c, am, nm, d, sp, wbs):
        parameters = self.algorithm_module.Parameters
        
        half_ssd = int(math.floor(s/2)) + 1
        half_ssd_further = s
        ssd_further = 2*s

        random_walk_short = list(range(2, half_ssd))
        random_walk_long = list(range(s+2, s+half_ssd))
        random_walk_short_for_further = list(range(2, half_ssd_further))
        random_walk_long_for_further = list(range(ssd_further+2, ssd_further+half_ssd_further))

        non_further = any(topo for topo in ['SourceCorner','Source2CornerTop','Source3CornerTop','SinkCorner','SinkCorner2Source','SinkCorner3Source'] if topo in parameters.configurations)

        further = any(topo for topo in ['FurtherSinkCorner','FurtherSinkCorner2Source','FurtherSinkCorner3Source'] if topo in parameters.configurations)

        #check the random-walk_tye.
        if len(parameters.random_walk_types) == 1:
            pass
        else:
            raise RuntimeError("only support ONE random_walk_type!")

        #set up the walk_short and walk_long
        if non_further and further:
            raise RuntimeError("Build other configurations with Further* configurations!")

        if non_further:
            if 'only_short_random_walk' in parameters.random_walk_types:
                walk_short = random_walk_short
                walk_long = random_walk_short

            elif 'only_long_random_walk' in parameters.random_walk_types:
                walk_short = random_walk_long
                walk_long = random_walk_long
        
            elif 'phantom_walkabouts' in parameters.random_walk_types:
                walk_short = random_walk_short
                walk_long = random_walk_long

            else:
                raise RuntimeError("error in the function: _short_long_walk_lengths")

        elif further:
            if 'only_short_random_walk' in parameters.random_walk_types:
                walk_short = random_walk_short_for_further
                walk_long = random_walk_short_for_further

            elif 'only_long_random_walk' in parameters.random_walk_types:
                walk_short = random_walk_long_for_further
                walk_long = random_walk_long_for_further
        
            elif 'phantom_walkabouts' in parameters.random_walk_types:
                walk_short = random_walk_short_for_further
                walk_long = random_walk_long_for_further

            else:
                raise RuntimeError("error in the function: _short_long_walk_lengths")
        
        else:
            raise RuntimeError("error in the function: _short_long_walk_lengths")

        return list(zip(walk_short, walk_long))
        
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
            parameters.source_periods, parameters.direction_biases, parameters.orders,
            parameters.short_counts, parameters.long_counts, parameters.wait_before_short
        )

        argument_product = [
            (s, c, am, nm, cm, fm, d, nido, lnst, sp, swl, lwl, db, o, sc, lc, wbs)

            for (s, c, am, nm, cm, fm, d, nido, lnst, sp, db, o, sc, lc, wbs) in argument_product

            for (swl,lwl) in self._short_long_walk_lengths(s, c, am, nm, d, sp, wbs)
        ]        

        argument_product = self.adjust_source_period_for_multi_source(argument_product)

        return argument_product


    def _run_table(self, args):
        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=('normal latency', 'ssd', 'captured', 'sent', 'received ratio'))

        result_table = fake_result.ResultTable(phantom_results)

        self._create_table("{}-results".format(self.algorithm_module.name), result_table)

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
        }

        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            source_period_normalisation="NumSources"
        )

        parameters = [
            ('source period', ' seconds'),
            ('long walk length', ' hops'),
            ('short walk length', ' hops')
        ]

        custom_yaxis_range_max = {
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

                if result_name in custom_yaxis_range_max:
                    g.yaxis_range_max = custom_yaxis_range_max[result_name]

                g.create(phantom_results)

                summary.GraphSummary(
                    os.path.join(self.algorithm_module.graphs_path, name),
                    self.algorithm_module.name + '-' + name
                ).run()

    def _run_scatter_graph(self, args):
        from data.graph import scatter

        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
        }

        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            source_period_normalisation="NumSources"
        )

        combine = ["short walk length", "long walk length"]

        for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():

            name = '{}-comb-{}'.format(yaxis.replace(" ", "_"), "=".join(combine).replace(" ", "-"))

            g = scatter.Grapher(
                self.algorithm_module.graphs_path, name,
                xaxis='network size', yaxis=yaxis, combine=combine,
                yextractor=scalar_extractor
            )

            g.xaxis_label = 'Network Size'
            g.yaxis_label = yaxis_label
            g.key_position = key_position

            g.create(phantom_results)

            summary.GraphSummary(
                self.algorithm_module.graphs_path,
                self.algorithm_module.name + '-' + name
            ).run()

    def _run_best_worst_average_graph(self, args):
        from data.graph import best_worst_average_versus

        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
        }

        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            source_period_normalisation="NumSources"
        )

        custom_yaxis_range_max = {
            'captured': 50,
            'sent': 20000
        }

        combine = ["short walk length", "long walk length"]

        for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():

            name = '{}-bwa-{}'.format(yaxis.replace(" ", "_"), "=".join(combine).replace(" ", "-"))

            g = best_worst_average_versus.Grapher(
                self.algorithm_module.graphs_path, name,
                xaxis='network size', yaxis=yaxis, vary=combine,
                yextractor=scalar_extractor
            )

            g.xaxis_label = 'Network Size'
            g.yaxis_label = yaxis_label
            g.key_position = key_position

            if yaxis in custom_yaxis_range_max:
                g.yaxis_range_max = custom_yaxis_range_max[yaxis]

            g.create(phantom_results)

            summary.GraphSummary(
                self.algorithm_module.graphs_path,
                self.algorithm_module.name + '-' + name
            ).run()

    def _run_average_graph(self, args):
        from data.graph import combine_versus

        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
        }

        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            source_period_normalisation="NumSources"
        )

        custom_yaxis_range_max = {
            'captured': 80,
            'sent': 30000
        }

        combine = ["short walk length", "long walk length"]

        parameters = [
            ('source period', ' seconds'),
        ]

        for (parameter_name, parameter_unit) in parameters:
            for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():

                name = '{}-v-{}-i-{}'.format(
                    yaxis.replace(" ", "_"),
                    parameter_name.replace(" ", "-"),
                    "=".join(combine).replace(" ", "-")
                )

                g = combine_versus.Grapher(
                    self.algorithm_module.graphs_path, name,
                    xaxis='network size', yaxis=yaxis, vary=parameter_name, combine=combine, combine_function=np.mean,
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
                    self.algorithm_module.graphs_path,
                    self.algorithm_module.name + '-' + name
                ).run()

    def run(self, args):
        args = super(CLI, self).run(args)

        if 'table' == args.mode:
            self._run_table(args)

        if 'graph' == args.mode:
            self._run_graph(args)

        if 'average-graph' == args.mode:
            self._run_average_graph(args)

        if 'scatter-graph' == args.mode:
            self._run_scatter_graph(args)

        if 'best-worst-average-graph' == args.mode:
            self._run_best_worst_average_graph(args)
