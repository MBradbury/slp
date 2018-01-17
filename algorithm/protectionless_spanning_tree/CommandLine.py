from __future__ import print_function

import os, itertools, datetime

from simulator.Simulation import Simulation
from simulator import CommandLineCommon

from data import results, latex
from data.table import safety_period, direct_comparison
from data.graph import summary, versus
from data.util import scalar_extractor

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__)

        subparser = self._subparsers.add_parser("graph")

    def _argument_product(self, sim, extras=None):
        parameters = self.algorithm_module.Parameters

        argument_product = itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models,
            parameters.communication_models, parameters.fault_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.source_periods
        )

        # Factor in the number of sources when selecting the source period.
        # This is done so that regardless of the number of sources the overall
        # network's normal message generation rate is the same.
        argument_product = self.adjust_source_period_for_multi_source(sim, argument_product)

        # Provide the argument to the attacker model
        argument_product = [
            (s, c, am.format(source_period=sp), nm, cm, fm, d, nido, lnst, sp)
            for (s, c, am, nm, cm, fm, d, nido, lnst, sp)
            in argument_product
        ]

        argument_product = self.add_extra_arguments(argument_product, extras)

        return argument_product


    def _cluster_time_estimator(self, sim, args, **kwargs):
        """Estimates how long simulations are run for. Override this in algorithm
        specific CommandLine if these values are too small or too big. In general
        these have been good amounts of time to run simulations for. You might want
        to adjust the number of repeats to get the simulation time in this range."""
        size = args['network size']
        if size == 11:
            return datetime.timedelta(hours=3)
        elif size == 15:
            return datetime.timedelta(hours=6)
        elif size == 21:
            return datetime.timedelta(hours=12)
        elif size == 25:
            return datetime.timedelta(hours=24)
        else:
            raise RuntimeError("No time estimate for network sizes other than 11, 15, 21 or 25")

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
            parameters=self.algorithm_module.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            source_period_normalisation="NumSources")

        for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
            name = '{}-v-configuration'.format(yaxis.replace(" ", "_"))

            g = versus.Grapher(
                self.algorithm_module.graphs_path, name,
                xaxis='network size', yaxis=yaxis, vary='configuration',
                yextractor=scalar_extractor)

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

        if 'graph' == args.mode:
            self._run_graph(args)
