from __future__ import print_function

import datetime
import itertools
import os.path

from simulator import CommandLineCommon

import algorithm

from data import results
from data.graph import summary, versus
from data.util import scalar_extractor

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(__package__)

        subparser = self._add_argument("table", self._run_table)
        subparser = self._add_argument("graph", self._run_graph)

    def _argument_product(self):
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
        argument_product = self.adjust_source_period_for_multi_source(argument_product)

        # Provide the argument to the attacker model
        argument_product = [
            (s, c, am.format(source_period=sp), nm, cm, fm, d, nido, lnst, sp)
            for (s, c, am, nm, cm, fm, d, nido, lnst, sp)
            in argument_product
        ]

        return argument_product


    def _cluster_time_estimator(self, args, **kwargs):
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
            'time taken': ('Time Taken (seconds)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            #'good move ratio': ('Good Move Ratio (%)', 'right top'),
            'norm(norm(sent,time taken),num_nodes)': ('Messages Sent per node per second', 'right top'),
        }

        varying = [
            (('network size', ''), ('source period', ' seconds')),
            (('network size', ''), ('communication model', '~')),
            (('network size', ''), ('configuration', '~')),
        ]

        custom_yaxis_range_max = {
            'received ratio': 100,
        }

        self._create_versus_graph(graph_parameters, varying, custom_yaxis_range_max,
            source_period_normalisation="NumSources",
            enerate_legend_graph=True
        )

    def _run_table(self, args):
        parameters = [
            'normal latency', 'ssd', 'captured', 'sent', 'received ratio'
        ]

        self._create_results_table(parameters)
