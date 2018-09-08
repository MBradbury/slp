from __future__ import print_function

from datetime import timedelta
import os

import algorithm

import simulator.sim
from simulator.Simulation import Simulation
from simulator import CommandLineCommon

from data import results, submodule_loader
from data.table import safety_period, direct_comparison, fake_result
from data.table.data_formatter import TableDataFormatter
from data.graph import summary, versus
from data.util import scalar_extractor
import data.testbed

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__()

        subparser = self._add_argument("table", self._run_table)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--show-stddev", action="store_true")
        subparser.add_argument("--show", action="store_true", default=False)
        subparser.add_argument("--testbed", type=str, choices=submodule_loader.list_available(data.testbed), default=None, help="Select the testbed to analyse. (Only if not analysing regular results.)")

        subparser = self._add_argument("graph", self._run_graph)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")

    def _cluster_time_estimator(self, sim, args, **kwargs):
        historical_key_names = ('network size', 'source period')

        if sim == "tossim":
            historical = {
                ('11', '0.125'): timedelta(seconds=2),
                ('11', '0.25'): timedelta(seconds=2),
                ('11', '0.5'): timedelta(seconds=2),
                ('11', '1.0'): timedelta(seconds=3),
                ('11', '2.0'): timedelta(seconds=3),
                ('15', '0.125'): timedelta(seconds=6),
                ('15', '0.25'): timedelta(seconds=6),
                ('15', '0.5'): timedelta(seconds=7),
                ('15', '1.0'): timedelta(seconds=8),
                ('15', '2.0'): timedelta(seconds=9),
                ('21', '0.125'): timedelta(seconds=31),
                ('21', '0.25'): timedelta(seconds=29),
                ('21', '0.5'): timedelta(seconds=32),
                ('21', '1.0'): timedelta(seconds=32),
                ('21', '2.0'): timedelta(seconds=34),
                ('25', '0.125'): timedelta(seconds=71),
                ('25', '0.25'): timedelta(seconds=70),
                ('25', '0.5'): timedelta(seconds=73),
                ('25', '1.0'): timedelta(seconds=82),
                ('25', '2.0'): timedelta(seconds=70),
            }
        else:
            historical = {}

        return self._cluster_time_estimator_from_historical(
            sim, args, kwargs, historical_key_names, historical,
            allowance=0.25
        )

    def _run_table(self, args):
        from data.table.summary_formatter import TableDataFormatter
        fmt = TableDataFormatter()

        parameters = [
            'repeats',
            'time taken',
            'received ratio',
            'captured',
            'normal latency',
            'norm(sent,time taken)',
            'attacker distance',
        ]

        def results_filter(params):
            return params["noise model"] != "casino-lab" or params["configuration"] != "SourceCorner" or params["source period"] == "0.125"

        hide_parameters = []#'buffer size', 'max walk length', 'pr direct to sink']
        caption_values = ["network size"]

        extractors = {
            # Just get the distance of attacker 0 from node 0 (the source in SourceCorner)
            "attacker distance": lambda yvalue: yvalue[(0, 0)]
        }

        self._create_results_table(args.sim, parameters,
            fmt=fmt, results_filter=results_filter, hide_parameters=hide_parameters, extractors=extractors, resize_to_width=True,
            caption_values=caption_values, show=args.show)

    def _run_graph(self, args):
        graph_parameters = {
            'time taken': ('Time Taken (seconds)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            #'good move ratio': ('Good Move Ratio (%)', 'right top'),
            'norm(norm(sent,time taken),network size)': ('Messages Sent per node per second', 'right top'),
        }

        varying = [
            (('network size', ''), ('source period', ' seconds')),
            (('network size', ''), ('communication model', '~')),
        ]

        custom_yaxis_range_max = {
            'received ratio': 100,
        }

        self._create_versus_graph(args.sim, graph_parameters, varying,
            custom_yaxis_range_max=custom_yaxis_range_max,
            #source_period_normalisation="NumSources"
        )
