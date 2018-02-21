
from datetime import timedelta
import itertools

import simulator.sim
from simulator import CommandLineCommon

import algorithm
protectionless = algorithm.import_algorithm("protectionless")

from data import results, submodule_loader
from data.table import fake_result

# Use the safety periods for SeqNosReactiveAttacker() if none are available for SeqNosOOOReactiveAttacker()
safety_period_equivalence = {
    "attacker model": {"SeqNosOOOReactiveAttacker()": "SeqNosReactiveAttacker()"}
}

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(protectionless.name, safety_period_equivalence=safety_period_equivalence)

        subparser = self._add_argument("table", self._run_table)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--show", action="store_true", default=False)

        subparser = self._add_argument("graph", self._run_graph)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")

    def _argument_product(self, sim, extras=None):
        parameters = self.algorithm_module.Parameters

        parameter_values = self._get_global_parameter_values(sim, parameters)
        parameter_values.append(parameters.buffer_sizes)
        parameter_values.append(parameters.max_walk_lengths)
        parameter_values.append(parameters.direct_to_sink_prs)
        parameter_values.append(parameters.msg_group_sizes)

        argument_product = list(itertools.product(*parameter_values))

        argument_product = self.add_extra_arguments(argument_product, extras)
        
        return argument_product

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 2.0

    def _cluster_time_estimator(self, sim, args, **kwargs):
        historical_key_names = ('network size', 'source period')

        if sim == "tossim":
            historical = {
                ('7', '0.25'): timedelta(seconds=1),
                ('7', '0.5'): timedelta(seconds=1),
                ('7', '1.0'): timedelta(seconds=1),
                ('7', '2.0'): timedelta(seconds=1),
                ('11', '0.25'): timedelta(seconds=1),
                ('11', '0.5'): timedelta(seconds=1),
                ('11', '1.0'): timedelta(seconds=1),
                ('11', '2.0'): timedelta(seconds=1),
                ('15', '0.25'): timedelta(seconds=2),
                ('15', '0.5'): timedelta(seconds=3),
                ('15', '1.0'): timedelta(seconds=3),
                ('15', '2.0'): timedelta(seconds=3),
                ('21', '0.25'): timedelta(seconds=13),
                ('21', '0.5'): timedelta(seconds=14),
                ('21', '1.0'): timedelta(seconds=15),
                ('21', '2.0'): timedelta(seconds=17),
                ('25', '0.25'): timedelta(seconds=26),
                ('25', '0.5'): timedelta(seconds=26),
                ('25', '1.0'): timedelta(seconds=28),
                ('25', '2.0'): timedelta(seconds=32),
            }
        else:
            historical = {}

        return self._cluster_time_estimator_from_historical(
            sim, args, kwargs, historical_key_names, historical,
            allowance=0.25,
            max_time=timedelta(days=2)
        )

    def _run_table(self, args):
        parameters = [
            'normal latency', 'ssd', 'captured',
            'received ratio', 'failed avoid sink',
            'failed avoid sink when captured',
        ]

        self._create_results_table(args.sim, parameters, show=args.show)

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            #'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            #'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'norm(sent,time taken)': ('Total Messages Sent per Second', 'left top'),
            #'failed avoid sink': ('Failed to Avoid Sink (%)', 'left top'),
            #'failed avoid sink when captured': ('Failed to Avoid Sink When Captured (%)', 'left top'),
        }

        varying = [
            (('network size', ''), ('msg group size', '')),
            #(('network size', ''), ('source period', ' seconds')),
            #(('network size', ''), ('pr direct to sink', '')),
        ]

        custom_yaxis_range_max = {
            'received ratio': 100,
            #'norm(sent,time taken)': 300,
            #'captured': 100,
            #'normal latency': 4000,
        }

        self._create_versus_graph(args.sim, graph_parameters, varying,
            custom_yaxis_range_max=custom_yaxis_range_max,
            xaxis_font = "',18'",
            yaxis_font = "',18'",
            xlabel_font = "',17'",
            ylabel_font = "',17'",
            line_width = 3,
            point_size = 2,
            nokey = True,
            generate_legend_graph = True,
            legend_font_size = 16,
        )
