from __future__ import print_function

import os, itertools

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

        # Provide the argument to the attacker model
        argument_product = [
            (s, c, am.format(source_period=sp), nm, cm, d, nido, lnst, sp)
            for (s, c, am, nm, cm, d, nido, lnst, sp)
            in argument_product
        ]

        return argument_product

    def time_taken_to_safety_period(self, time_taken):
        return time_taken * 2.0


    def _run_table(self, args):
        safety_period_table = safety_period.TableGenerator(self.algorithm_module.result_file_path)

        prod = itertools.product(Simulation.available_noise_models(),
                                 Simulation.available_communication_models())

        for (noise_model, comm_model) in prod:

            print("Writing results table for the {} noise model and {} communication model".format(noise_model, comm_model))

            filename = '{}-{}-{}-results'.format(self.algorithm_module.name, noise_model, comm_model)

            self._create_table(filename, safety_period_table,
                               param_filter=lambda (cm, nm, am, c, d): nm == noise_model and cm == comm_model)

    def _run_graph(self, args):
        graph_parameters = {
            'safety period': ('Safety Period (seconds)', 'left top'),
            'time taken': ('Time Taken (seconds)', 'left top'),
            #'ssd': ('Sink-Source Distance (hops)', 'left top'),
            #'captured': ('Capture Ratio (%)', 'left top'),
            #'sent': ('Total Messages Sent', 'left top'),
            #'received ratio': ('Receive Ratio (%)', 'left bottom'),
        }

        protectionless_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            source_period_normalisation="NumSources")

        for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
            name = '{}-v-configuration'.format(yaxis.replace(" ", "_"))

            yextractor = lambda x: scalar_extractor(x.get((0, 0), None)) if yaxis == 'attacker distance' else scalar_extractor(x)

            g = versus.Grapher(
                self.algorithm_module.graphs_path, name,
                xaxis='network size', yaxis=yaxis, vary='configuration',
                yextractor=yextractor)

            g.generate_legend_graph = True

            g.xaxis_label = 'Network Size'
            g.yaxis_label = yaxis_label
            g.vary_label = ''
            g.vary_prefix = ''

            g.nokey = True
            g.key_position = key_position

            g.create(protectionless_results)

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path, name),
                '{}-{}'.format(self.algorithm_module.name, name)
            ).run()

    def run(self, args):
        args = super(CLI, self).run(args)

        if 'table' == args.mode:
            self._run_table(args)

        if 'graph' == args.mode:
            self._run_graph(args)
