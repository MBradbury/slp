from __future__ import print_function, division

import datetime
import itertools
import math
import os.path

import numpy as np

from simulator import CommandLineCommon
from simulator import Configuration

import algorithm
protectionless = algorithm.import_algorithm("protectionless")
phantom_chen = algorithm.import_algorithm("phantom_chen")
ilprouting_chen = algorithm.import_algorithm("ilprouting_chen")
adaptive_spr_notify_chen = algorithm.import_algorithm("adaptive_spr_notify_chen")
protectionless_chen = algorithm.import_algorithm("protectionless_chen")
protectionless_ctp_chen = algorithm.import_algorithm("protectionless_ctp_chen")


from data import results, submodule_loader

from data.table import safety_period, fake_result
from data.graph import summary, versus, min_max_versus
from data.util import scalar_extractor, useful_log10

from data.run.common import RunSimulationsCommon

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(protectionless.name)

        subparser = self._add_argument("table", self._run_table)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--show", action="store_true", default=False)

        subparser = self._add_argument("graph", self._run_graph)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")

        subparser = self._add_argument("graph-min-max", self._run_min_max_versus)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")

        subparser = self._add_argument("graph-multi", self._run_multi_versus)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")

    def _cluster_time_estimator(self, sim, args, **kwargs):
        """Estimates how long simulations are run for. Override this in algorithm
        specific CommandLine if these values are too small or too big. In general
        these have been good amounts of time to run simulations for. You might want
        to adjust the number of repeats to get the simulation time in this range."""
        size = args['network size']
        if size == 11:
            return datetime.timedelta(hours=4)
        elif size == 15:
            return datetime.timedelta(hours=8)
        elif size == 21:
            return datetime.timedelta(hours=16)
        elif size == 25:
            return datetime.timedelta(hours=32)
        else:
            raise RuntimeError("No time estimate for network sizes other than 11, 15, 21 or 25")

    def _argument_product(self, sim, extras=None):
        parameters = self.algorithm_module.Parameters

        argument_product = itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models,
            parameters.communication_models, parameters.fault_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.source_periods,
            parameters.safety_factors,
            parameters.orders,
            parameters.short_counts, parameters.long_counts, parameters.wait_before_short,
            parameters.buffer_sizes,
        )       

        argument_product = self.add_extra_arguments(argument_product, extras)

        argument_product = self.adjust_source_period_for_multi_source(sim, argument_product)

        return argument_product

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 1.0

    def _run_table(self, args):
        phantom_walkabouts_results = results.Results(
            args.sim, self.algorithm_module.result_file_path(args.sim),
            parameters=self.algorithm_module.local_parameter_names,
            results=('normal latency', 'ssd', 'captured', 'sent', 'received ratio'))

        result_table = fake_result.ResultTable(phantom_walkabouts_results)

        self._create_table("{}-results".format(self.algorithm_module.name), result_table, orientation='landscape', show=args.show)

    @staticmethod
    def vvalue_converter(name):
        try:
            (bias, order, short_count, long_count, wait) = name

            if short_count == 1 and long_count == 0:
                return "(1, 0)"
            elif short_count == 1 and long_count == 1:
                return "(1, 1)"
            elif short_count == 1 and long_count == 2:
                return "(1, 2)"
            else:
                return name
        except ValueError:
            return name

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left bottom'),
            'captured': ('Capture Ratio (%)', 'left right'),
            #'sent': ('Total Messages Sent', 'left top'),
            'norm(sent,time taken)': ('Messages Sent per Second', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            #'utility animal': ('Utility (Animal)', 'left top'),
            #'utility monitor': ('Utility (Monitor)', 'left top'),
            #'utility military': ('Utility (Military)', 'left top'),
        }

        varying = [
            #(('network size', ''), (('direction bias', 'order', 'short count', 'long count', 'wait before short'), '')),
            #(('safety factor', ''), (('direction bias', 'order', 'short count', 'long count', 'wait before short'), '')),
            (('network size', ''), ('source period', '')),
        ]

        custom_yaxis_range_max = {
            'captured': 50,
            'received ratio': 100,
            'normal latency': 1000,
            'norm(sent,time taken)': 2000
        }

        def filter_params(all_params):
            return all_params['safety factor'] != '1.3'


        self._create_versus_graph(args.sim, graph_parameters, varying, custom_yaxis_range_max,
            #source_period_normalisation="NumSources",
            #results_filter=filter_params,
            #vary_label='PW',
            #vvalue_label_converter=self.vvalue_converter,
        )

    def _run_min_max_versus(self, args):
        graph_parameters = {
            #'normal latency': ('Normal Message Latency (milliseconds)', 'left bottom'),
            'captured': ('Capture Ratio (%)', 'left top'),
            'norm(sent,time taken)': ('Messages Transmission (messages)', 'right top'),
            'received ratio': ('Delivery Ratio (%)', 'left bottom'),
            'utility animal': ('Utility (Animal Protection)', 'right top'),
            'utility monitor': ('Utility (Asset Monitor)', 'right bottom'),
            'utility military': ('Utility (Military)', 'right bottom'),
            'normalised captured': ('Normalised Capture Ratio', 'left top'),
            'normalised norm(sent,time taken)': ('Normalised Messages Transmission', 'right top'),
        }

        varying = [
            (('safety factor', ''), (('direction bias', 'order', 'short count', 'long count', 'wait before short'), '')),
        ]
        
        custom_yaxis_range_max = {
            #'normal latency': 500,
            #'norm(sent,time taken)': 600,
            'received ratio': 100,
            'capture ratio': 100,
            'utility animal': 1.0,
            'utility monitor': 1.0,
            'utility military': 1.0,
            #'normalised captured': 2.0,
            #'normalised norm(sent,time taken)': 2000
        }

        key_equivalence = {
            "attacker model": {"SeqNosReactiveAttacker()": "SeqNosOOOReactiveAttacker()"}
        }

        args = (
            [protectionless_chen, protectionless_ctp_chen, phantom_chen, ilprouting_chen, adaptive_spr_notify_chen],
            None, graph_parameters, varying, None, custom_yaxis_range_max,
        )

        kwargs = {
            "min_label": ["Protectionless - Min", "ProtectionlessCTP - Min","Phantom - Min", "ILP - Min", "AdaptiveSPR - Min"],
            "max_label": ["Protectionless - Max", "ProtectionlessCTP - Max", "Phantom - Max", "ILP - Max", "AdaptiveSPR - Max"],
            "min_max_same_label": ["Protectionless", "ProtectionlessCTP", "Phantom", "ILP", "AdaptiveSPR"],
            "vary_label": "",
            "comparison_label": "PW",
            "vvalue_label_converter": self.vvalue_converter,
            "key_equivalence": key_equivalence,
            "nokey": True,
            "generate_legend_graph": True,
        }

        self._create_min_max_versus_graph(args.sim, *args, **kwargs)

        graph_parameters = {
            'normal latency': ('Normal Message Latency (milliseconds)', 'left bottom'),
        }

        args = (
            [protectionless_chen, protectionless_ctp_chen, phantom_chen, ilprouting_chen, adaptive_spr_notify_chen],
            None, graph_parameters, varying, None, custom_yaxis_range_max,
        )

        # For latency generate graphs with log10 yaxis scale
        self._create_min_max_versus_graph(args.sim, *args, yaxis_logscale=10, yaxis_range_min=10, **kwargs)

    def _run_multi_versus(self, args):
        graph_parameters = [
            ('utility animal', 'Utility (Animal)'),
            ('utility monitor', 'Utility (Monitor)'),
            ('utility military', 'Utility (Military)'),
        ]

        varying = [
            ('safety factor', ''),
        ]
        
        custom_yaxis_range_max = 1.0

        self._create_multi_versus_graph(
            args.sim, graph_parameters, varying, "Utility (\\%)", custom_yaxis_range_max
        )
