from __future__ import print_function

import itertools
import os

from simulator import CommandLineCommon

import algorithm

protectionless = algorithm.import_algorithm("protectionless")
adaptive = algorithm.import_algorithm("adaptive")

from data import results

from data.table import safety_period, fake_result
from data.graph import summary, versus, min_max_versus, dual_min_max_versus
from data.util import scalar_extractor

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(protectionless.name)

        subparser = self._add_argument("table", self._run_table)
        subparser = self._add_argument("graph", self._run_graph)
        subparser = self._add_argument("min-max-versus", self._run_min_max_versus)
        subparser = self._add_argument("dual-min-max-versus", self._run_dual_min_max_versus)

    def _argument_product(self, sim, extras=None):
        parameters = self.algorithm_module.Parameters

        argument_product = list(filter(
            lambda x: x[10] in parameters.walk_hop_lengths[x[0]],
            itertools.product(
                parameters.sizes, parameters.configurations,
                parameters.attacker_models, parameters.noise_models, parameters.communication_models, parameters.fault_models,
                [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
                parameters.source_periods,
                set(itertools.chain(*parameters.walk_hop_lengths.values())), parameters.landmark_nodes
            )
        ))

        argument_product = self.add_extra_arguments(argument_product, extras)

        # Factor in the number of sources when selecting the source period.
        # This is done so that regardless of the number of sources the overall
        # network's normal message generation rate is the same.
        argument_product = self.adjust_source_period_for_multi_source(sim, argument_product)

        return argument_product

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 2.0


    def _run_table(self, args):
        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=('normal latency', 'ssd', 'captured', 'sent', 'received ratio', 'paths reached end', 'source dropped'))

        result_table = fake_result.ResultTable(phantom_results)

        self._create_table("{}-results".format(self.algorithm_module.name), result_table)

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
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
            parameters=self.algorithm_module.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            network_size_normalisation="UseNumNodes"
        )

        parameters = [
            ('source period', ' seconds'),
            ('walk length', ' hops')
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
                    os.path.join(algorithm.results_directory_name, self.algorithm_module.name + '-' + name)
                ).run()

    def _run_min_max_versus(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'at 17.5,290'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
            'sent': ('Total Messages Sent', 'left top'),
            'norm(norm(sent,time taken),num_nodes)': ('Total Messages Sent per node per second', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'right top'),
            'energy impact per node per second': ('Energy Impact per Node per second (mAh s^{-1})', 'left top'),
            'energy allowance used': ('Energy Allowance Used (\%)', 'left top'),
        }

        custom_yaxis_range_max = {
            'sent': 450000,
            'captured': 40,
            'received ratio': 100,
            'normal latency': 300,
            'norm(norm(sent,time taken),num_nodes)': 30,
            'energy allowance used': 100,
        }

        nokey = {'captured', 'sent', 'received ratio',
                 'norm(norm(sent,time taken),num_nodes)', 'energy allowance used'}

        protectionless_results = results.Results(
            protectionless.result_file_path,
            parameters=tuple(),
            results=graph_parameters.keys(),
            network_size_normalisation="UseNumNodes"
        )

        adaptive_results = results.Results(
            adaptive.result_file_path,
            parameters=('approach',),
            results=graph_parameters.keys(),
            network_size_normalisation="UseNumNodes"
        )

        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=graph_parameters.keys(),
            network_size_normalisation="UseNumNodes"
        )

        def graph_min_max_versus(result_name):
            name = 'min-max-{}-versus-{}'.format(result_name, adaptive.name)

            g = min_max_versus.Grapher(
                self.algorithm_module.graphs_path, name,
                xaxis='network size', yaxis=result_name, vary='walk length', yextractor=scalar_extractor)

            g.xaxis_label = 'Number of Nodes'
            g.yaxis_label = graph_parameters[result_name][0]
            g.key_position = graph_parameters[result_name][1]

            g.nokey = result_name in nokey

            g.min_label = 'Dynamic - Lowest'
            g.max_label = 'Dynamic - Highest'
            g.comparison_label = 'Phantom'
            g.baseline_label = 'Protectionless - Baseline'
            g.vary_label = ''

            g.generate_legend_graph = True

            g.point_size = 1.3
            g.line_width = 4
            g.yaxis_font = "',14'"
            g.xaxis_font = "',12'"

            if result_name in custom_yaxis_range_max:
                g.yaxis_range_max = custom_yaxis_range_max[result_name]

            g.vvalue_label_converter = lambda value: "W_h = {}".format(value)

            g.create(adaptive_results, phantom_results, protectionless_results)

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                os.path.join(algorithm.results_directory_name, '{}-{}'.format(self.algorithm_module.name, name).replace(" ", "_"))
            ).run()

        for result_name in graph_parameters.keys():
            graph_min_max_versus(result_name)

    def _run_dual_min_max_versus(self, args):
        graph_parameters = {
            ('norm(norm(sent,time taken),num_nodes)', 'energy allowance used'): ('Total Messages Sent per node per second', 'Energy Allowance Used (\%)', 'right top'),
        }

        sample_energy_allowance_used = 23.2076127193
        sample_sent_per_node_per_sec = 4.28833268899

        custom_yaxis_range_max = {
            # Calculated so that the scale matches the energy allowance used scale exactly using two reference values
            'norm(norm(sent,time taken),num_nodes)': sample_sent_per_node_per_sec / (sample_energy_allowance_used / 100),

            'energy allowance used': 100,
        }

        results_to_load = [param for sublist in graph_parameters.keys() for param in sublist]

        protectionless_results = results.Results(
            protectionless.result_file_path,
            parameters=tuple(),
            results=results_to_load,
            network_size_normalisation="UseNumNodes"
        )

        adaptive_results = results.Results(
            adaptive.result_file_path,
            parameters=('approach',),
            results=results_to_load,
            network_size_normalisation="UseNumNodes"
        )

        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=results_to_load,
            network_size_normalisation="UseNumNodes"
        )

        def graph_dual_min_max_versus(result_name1, result_name2, xaxis):
            name = 'dual-min-max-{}-versus-{}_{}-{}'.format(adaptive.name, result_name1, result_name2, xaxis)

            g = dual_min_max_versus.Grapher(
                self.algorithm_module.graphs_path, name,
                xaxis=xaxis, yaxis1=result_name1, yaxis2=result_name2, vary='walk length', yextractor=scalar_extractor)

            g.xaxis_label = xaxis.title()
            g.yaxis1_label = graph_parameters[(result_name1, result_name2)][0]
            g.yaxis2_label = graph_parameters[(result_name1, result_name2)][1]
            g.key_position = graph_parameters[(result_name1, result_name2)][2]

            g.yaxis_font = g.xaxis_font = "',15'"

            g.nokey = True

            g.generate_legend_graph = True

            g.point_size = 1.3
            g.line_width = 4
            g.yaxis_font = "',14'"
            g.xaxis_font = "',12'"

            g.min_label = 'Dynamic - Lowest'
            g.max_label = 'Dynamic - Highest'
            g.comparison_label = 'Phantom'
            g.baseline_label = 'Protectionless - Baseline'
            g.vary_label = ''

            g.only_show_yaxis1 = True

            if result_name1 in custom_yaxis_range_max:
                g.yaxis1_range_max = custom_yaxis_range_max[result_name1]

            if result_name2 in custom_yaxis_range_max:
                g.yaxis2_range_max = custom_yaxis_range_max[result_name2]

            g.vvalue_label_converter = lambda value: "W_h = {}".format(value)

            g.create(adaptive_results, phantom_results, baseline_results=protectionless_results)

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                os.path.join(algorithm.results_directory_name, '{}-{}'.format(self.algorithm_module.name, name).replace(" ", "_"))
            ).run()

        for (result_name1, result_name2) in graph_parameters.keys():
            graph_dual_min_max_versus(result_name1, result_name2, 'network size')

    def run(self, args):
        args = super(CLI, self).run(args)

        if 'table' == args.mode:
            self._run_table(args)

        if 'graph' == args.mode:
            self._run_graph(args)

        if 'min-max-versus' == args.mode:
            self._run_min_max_versus(args)

        if 'dual-min-max-versus' == args.mode:
            self._run_dual_min_max_versus(args)
