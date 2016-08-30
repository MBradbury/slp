from __future__ import print_function

import itertools
import os

from simulator.Simulation import Simulation
from simulator import CommandLineCommon

from data import results, latex
from data.table import safety_period, direct_comparison
from data.graph import summary, versus
from data.util import scalar_extractor

class CLI(CommandLineCommon.CLI):

    local_parameter_names = tuple()

    def __init__(self):
        super(CLI, self).__init__(__package__)

        subparser = self._subparsers.add_parser("table")
        subparser = self._subparsers.add_parser("graph")
        subparser = self._subparsers.add_parser("ccpe-comparison-table")
        subparser = self._subparsers.add_parser("ccpe-comparison-graph")

    def _argument_product(self):
        parameters = self.algorithm_module.Parameters

        argument_product = itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models, parameters.communication_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.source_periods
        )

        # Factor in the number of sources when selecting the source period.
        # This is done so that regardless of the number of sources the overall
        # network's normal message generation rate is the same.
        argument_product = self.adjust_source_period_for_multi_source(argument_product)

        return argument_product        


    def _run_table(self, args):
        time_taken_to_safety_period = lambda time_taken: time_taken * 2.0

        safety_period_table = safety_period.TableGenerator(self.algorithm_module.result_file_path, time_taken_to_safety_period)

        prod = itertools.product(Simulation.available_noise_models(),
                                 Simulation.available_communication_models())

        for (noise_model, comm_model) in prod:

            print("Writing results table for the {} noise model and {} communication model".format(noise_model, comm_model))

            filename = '{}-{}-{}-results'.format(self.algorithm_module.name, noise_model, comm_model)

            self._create_table(filename, safety_period_table,
                               param_filter=lambda (cm, nm, am, c, d): nm == noise_model and cm == comm_model)

    def _run_graph(self, args):
        graph_parameters = {
            #'safety period': ('Safety Period (seconds)', 'left top'),
            #'time taken': ('Time Taken (seconds)', 'left top'),
            #'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            #'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'good move ratio': ('Good Move Ratio (%)', 'right top'),
            'norm(norm(sent,time taken),num_nodes)': ('Messages Sent per node per second', 'right top'),
        }

        protectionless_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            source_period_normalisation="NumSources")

        varying = [
            ("source period", " seconds"),
            ("communication model", "~")
        ]

        error_bars = set() # {'received ratio', 'good move ratio', 'norm(norm(sent,time taken),num_nodes)'}

        for (vary, vary_prefix) in varying:
            for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                name = '{}-v-{}'.format(yaxis.replace(" ", "_"), vary.replace(" ", "_"))

                yextractor = lambda x: scalar_extractor(x.get((0, 0), None)) if yaxis == 'attacker distance' else scalar_extractor(x)

                g = versus.Grapher(
                    self.algorithm_module.graphs_path, name,
                    xaxis='network size', yaxis=yaxis, vary=vary,
                    yextractor=yextractor)

                #g.generate_legend_graph = True

                g.xaxis_label = 'Network Size'
                g.vary_label = vary.title()
                g.vary_prefix = vary_prefix

                g.error_bars = yaxis in error_bars

                #g.nokey = True
                g.key_position = key_position

                g.create(protectionless_results)

                summary.GraphSummary(
                    os.path.join(self.algorithm_module.graphs_path, name),
                    '{}-{}'.format(self.algorithm_module.name, name)
                ).run()

    def _run_ccpe_comparison_table(self, args):
        from data.old_results import OldResults

        old_results = OldResults(
            'results/CCPE/protectionless-results.csv',
            parameters=tuple(),
            results=('time taken', 'received ratio', 'safety period')
        )

        protectionless_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=('time taken', 'received ratio', 'safety period')
        )

        result_table = direct_comparison.ResultTable(old_results, protectionless_results)

        self._create_table('{}-ccpe-comparison'.format(self.algorithm_module.name), result_table)

    def _run_ccpe_comparison_graphs(self, args):
        from data.old_results import OldResults

        result_names = ('time taken', 'received ratio', 'safety period')

        old_results = OldResults(
            'results/CCPE/protectionless-results.csv',
            parameters=self.local_parameter_names,
            results=result_names
        )

        protectionless_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=result_names
        )

        result_table = direct_comparison.ResultTable(old_results, protectionless_results)

        def create_ccpe_comp_versus(yxaxis, pc=False):
            name = 'ccpe-comp-{}-{}'.format(yxaxis, "pcdiff" if pc else "diff")

            versus.Grapher(
                self.algorithm_module.graphs_path, name,
                xaxis='network size', yaxis=yxaxis, vary='source period',
                yextractor=lambda (diff, pcdiff): pcdiff if pc else diff
            ).create(result_table)

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                '{}-{}'.format(self.algorithm_module.name, name).replace(" ", "_")
            ).run()

        for result_name in result_names:
            create_ccpe_comp_versus(result_name, pc=True)
            create_ccpe_comp_versus(result_name, pc=False)

    def run(self, args):
        args = super(CLI, self).run(args)

        if 'table' == args.mode:
            self._run_table(args)

        if 'graph' == args.mode:
            self._run_graph(args)

        if 'ccpe-comparison-table' == args.mode:
            self._run_ccpe_comparison_table(args)

        if 'ccpe-comparison-graph' == args.mode:
            self._run_ccpe_comparison_graphs(args)
