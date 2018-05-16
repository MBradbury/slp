
import datetime
import itertools

import simulator.sim
from simulator import CommandLineCommon

import algorithm
protectionless = algorithm.import_algorithm("protectionless")

from data import submodule_loader
from data.util import scalar_extractor

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(protectionless.name)

        subparser = self._add_argument("table", self._run_table)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--show", action="store_true", default=False)
        
        subparser = self._add_argument("graph", self._run_graph)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")

        subparser = self._add_argument("min-max-versus", self._run_min_max_versus)
        subparser = self._add_argument("dual-min-max-versus", self._run_dual_min_max_versus)
        subparser = self._add_argument("graph-sf", self._run_graph_safety_factor)

    def _cluster_time_estimator(self, sim, args, **kwargs):
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
        
    def _argument_product(self, sim, extras=None):
        parameters = self.algorithm_module.Parameters

        argument_product = list(itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models,
            parameters.communication_models, parameters.fault_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.source_periods, parameters.quiet_node_distance, parameters.safety_factors
        ))

        argument_product = self.add_extra_arguments(argument_product, extras)

        argument_product = self.adjust_source_period_for_multi_source(sim, argument_product)

        return argument_product

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 1.0


    def _run_table(self, args):
        parameters = [
            #'normal latency', 
            #'sent', 
            'captured',
            'received ratio',
            #'attacker distance wrt src',
            #'attacker distance',
            #'failed avoid sink',
            #'failed avoid sink when captured',
        ]

        self._create_results_table(args.sim, parameters, show=args.show)

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Message Latency (msec)', 'left top'),
            #'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            #'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'norm(sent,time taken)': ('Messages Transmission (messages)', 'left top'),
            #'attacker distance': ('Attacker Distance From Source (Meters)', 'left top'),
            #'failed avoid sink': ('Failed to Avoid Sink (%)', 'left top'),
            #'failed avoid sink when captured': ('Failed to Avoid Sink When Captured (%)', 'left top'),
        }

        varying = [
            #(('network size', ''), ('source period', '')),
            (('network size', ''), ('quiet node distance', '')),
        ]

        custom_yaxis_range_max = {
            'captured': 100,
            'received ratio': 100,
            'normal latency': 300,
            'norm(sent,time taken)': 2500
        }           

        yextractors = { }      

        self._create_versus_graph(args.sim, graph_parameters, varying,
            custom_yaxis_range_max=custom_yaxis_range_max,
            yextractor = yextractors,
            xaxis_font = "',16'",
            yaxis_font = "',16'",
            xlabel_font = "',18'",
            ylabel_font = "',16'",
            line_width = 3,
            point_size = 1,
            nokey = True,
            generate_legend_graph = True,
            legend_font_size = 16,
        )

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

    def _run_graph_safety_factor(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (seconds)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
            'norm(sent,time taken)': ('Messages Sent per Second', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'utility equal': ('Utility (Equal)', 'right top'),
            'utility animal': ('Utility (Animal)', 'right top'),
            'utility battle': ('Utility (Battle)', 'right top'),
        }

        varying = [
            (('safety factor', ''), (('walk length'), '')),
        ]

        custom_yaxis_range_max = {
            'normal latency': 500,
            'norm(sent,time taken)': 600,
            'received ratio': 100,
            'capture ratio': 100,
            'utility equal': 0.8,
            'utility animal': 0.8,
            'utility battle': 0.8,

        }

        def vvalue_converter(name):
            (bias, order, short_count, long_count, wait) = name

            if short_count == 1 and long_count == 0:
                return "PW(1, 0)"
            elif short_count == 1 and long_count == 1:
                return "PW(1, 1)"
            elif short_count == 1 and long_count == 2:
                return "PW(1, 2)"
            else:
                return name

        self._create_versus_graph(graph_parameters, varying, custom_yaxis_range_max,
            source_period_normalisation="NumSources",
            vary_label='',
            #vvalue_label_converter=vvalue_converter,
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

