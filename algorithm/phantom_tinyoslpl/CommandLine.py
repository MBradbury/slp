
import itertools
import os

import simulator.sim
from simulator import CommandLineCommon

import algorithm
protectionless = algorithm.import_algorithm("protectionless")

from data import submodule_loader, results
from data.table import fake_result
from data.graph import summary, versus, min_max_versus, dual_min_max_versus
from data.util import scalar_extractor

safety_period_equivalence = {
    "low power listening": {"enabled": "disabled"}
}

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super().__init__(protectionless.name, safety_period_equivalence=safety_period_equivalence)

        subparser = self._add_argument("table", self._run_table)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--show", action="store_true", default=False)

        subparser = self._add_argument("graph", self._run_graph)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")

        subparser = self._add_argument("min-max-versus", self._run_min_max_versus)

    def _argument_product(self, sim, extras=None):
        parameters = self.algorithm_module.Parameters

        # Some complexity as the walk hop length is determined by the network size
        network_size_index = sim.global_parameter_names.index('network size')
        walk_hop_length_index = len(sim.global_parameter_names)

        parameter_values = self._get_global_parameter_values(sim, parameters)
        parameter_values.append(set(itertools.chain(*parameters.walk_hop_lengths.values())))
        parameter_values.append(parameters.landmark_nodes)

        my_paramater_names = self.algorithm_module.extra_parameter_names
        my_paramater_values = [self._get_local_parameter_values(parameters, parameter) for parameter in my_paramater_names]

        argument_product = [
            x + y
            for x in itertools.product(*parameter_values)
            for y in zip(*my_paramater_values)
        ]

        # Remove incorrect combinations of walk hop lengths
        argument_product = [
            x for x in argument_product
            if x[walk_hop_length_index] in parameters.walk_hop_lengths[x[network_size_index]]
        ]

        argument_product = self.add_extra_arguments(argument_product, extras)

        # Factor in the number of sources when selecting the source period.
        # This is done so that regardless of the number of sources the overall
        # network's normal message generation rate is the same.
        argument_product = self.adjust_source_period_for_multi_source(sim, argument_product)

        return argument_product

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 2.0


    def _run_table(self, args):
        from data.table.summary_formatter import TableDataFormatter
        fmt = TableDataFormatter()

        parameters = [
            'captured',
            'received ratio',
            'paths reached end',
            'source dropped',
            #'path dropped',
            'normal latency',
            'ssd',
            'sent',
            'norm(sent,time taken)',
            'attacker distance',
        ]

        hide_parameters = []
 
        extractors = {
            # Just get the distance of attacker 0 from node 0 (the source in SourceCorner)
            "attacker distance": lambda yvalue: yvalue[(0, 0)]
        }

        self._create_results_table(args.sim, parameters,
            fmt=fmt, hide_parameters=hide_parameters, extractors=extractors,
            orientation="landscape",
            show=args.show)

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

    def run(self, args):
        args = super(CLI, self).run(args)

        if 'table' == args.mode:
            self._run_table(args)

        if 'graph' == args.mode:
            self._run_graph(args)

        if 'min-max-versus' == args.mode:
            self._run_min_max_versus(args)
