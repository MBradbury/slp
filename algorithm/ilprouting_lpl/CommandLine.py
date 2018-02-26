
from datetime import timedelta
import itertools

import simulator.sim
from simulator import CommandLineCommon

import algorithm
protectionless = algorithm.import_algorithm("protectionless")

from data import submodule_loader

# Use the safety periods for SeqNosReactiveAttacker() if none are available for SeqNosOOOReactiveAttacker()
safety_period_equivalence = {
    "attacker model": {"SeqNosOOOReactiveAttacker()": "SeqNosReactiveAttacker()",
                       "SeqNosOOOReactiveAttacker(message_detect='within_range(4.75)')": "SeqNosReactiveAttacker(message_detect='within_range(4.75)')"},
    "low power listening": {"enabled": "disabled"},
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

        custom_mapping = {"pr direct to sink": "direct_to_sink_prs"}

        for parameter in self.algorithm_module.base_parameter_names:
             parameter_values.append(self._get_local_parameter_values(parameters, parameter, custom_mapping=custom_mapping))

        my_paramater_names = ('lpl local wakeup', 'lpl remote wakeup', 'lpl delay after receive', 'lpl max cca checks')
        my_paramater_values = [self._get_local_parameter_values(parameters, parameter) for parameter in my_paramater_names]

        argument_product = [
            x + y
            for x in itertools.product(*parameter_values)
            for y in zip(*my_paramater_values)
        ]

        argument_product = self.add_extra_arguments(argument_product, extras)
        
        return argument_product

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 2.0

    def _run_table(self, args):
        parameters = [
            'normal latency', 'ssd', 'captured',
            'received ratio', 'failed avoid sink',
            'failed avoid sink when captured',
        ]

        self._create_results_table(args.sim, parameters, show=args.show)

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (seconds)', 'left top'),
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
            (('pr direct to sink', ''), ('msg group size', '')),
            #(('network size', ''), ('source period', ' seconds')),
            #(('network size', ''), ('pr direct to sink', '')),
        ]

        custom_yaxis_range_max = {
            'received ratio': 100,
            'norm(sent,time taken)': 500,
            'captured': 25,
            'normal latency': 4000,
        }

        self._create_versus_graph(args.sim, graph_parameters, varying,
            custom_yaxis_range_max=custom_yaxis_range_max,
            xaxis_font = "',16'",
            yaxis_font = "',16'",
            xlabel_font = "',18'",
            ylabel_font = "',18'",
            line_width = 3,
            point_size = 2,
            nokey = True,
            generate_legend_graph = True,
            legend_font_size = 16,
        )
