
from datetime import timedelta
import itertools
import os.path

from simulator import CommandLineCommon
import simulator.sim

import algorithm
protectionless = algorithm.import_algorithm("protectionless")

from data import results, submodule_loader
from data.table import fake_result
from data.graph import summary, min_max_versus
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

    def _argument_product(self, sim, extras=None):
        parameters = self.algorithm_module.Parameters

        parameter_values = self._get_global_parameter_values(sim, parameters)

        for parameter in self.algorithm_module.base_parameter_names:
             parameter_values.append(self._get_local_parameter_values(parameters, parameter))

        my_paramater_names = ('lpl normal early', 'lpl normal late', 'lpl fake early', 'lpl fake late', 'lpl choose early', 'lpl choose late')
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
        adaptive_results = results.Results(
            args.sim, self.algorithm_module.result_file_path(args.sim),
            parameters=self.algorithm_module.local_parameter_names,
            results=(
                'sent',
                #'delivered',
                'time taken',
                'normal latency',
                #'ssd',
                'captured',
                'fake', 'received ratio',
                'average duty cycle',
                # 'tfs', 'pfs',
                #'norm(sent,time taken)', 'norm(norm(sent,time taken),network size)',
                #'norm(norm(norm(sent,time taken),network size),source rate)'
            ))

        result_table = fake_result.ResultTable(adaptive_results)

        self._create_table(self.algorithm_module.name + "-results", result_table, show=args.show, orientation='landscape')

    def _run_graph(self, args):
        graph_parameters = {
            #'normal latency': ('Normal Message Latency (ms)', 'left top'),
            #'ssd': ('Sink-Source Distance (hops)', 'left top'),
            #'captured': ('Capture Ratio (%)', 'left top'),
            #'fake': ('Fake Messages Sent', 'left top'),
            #'sent': ('Total Messages Sent', 'left top'),
            #'received ratio': ('Receive Ratio (%)', 'left bottom'),
            #'tfs': ('Number of TFS Created', 'left top'),
            #'pfs': ('Number of PFS Created', 'left top'),
            #'tailfs': ('Number of TailFS Created', 'left top'),
            #'attacker distance': ('Attacker Distance From Source (Meters)', 'left top'),
            'average duty cycle': ('Average duty cycle', 'right top'),
            'norm(norm(sent,time taken),network size)': ('Messages Sent per Second per Node', 'left top'),
            'norm(norm(fake,time taken),network size)': ('Fake Messages Sent per Second per node', 'left top'),
        }

        varying = [
            (('network size', ''), ('source period', ' seconds')),
            #(('network size', ''), ('communication model', '~')),
        ]

        custom_yaxis_range_max = {
            'received ratio': 100,
        }

        yextractors = {
            # Just get the distance of attacker 0 from node 0 (the source in SourceCorner)
            "attacker distance": lambda yvalue: scalar_extractor(yvalue)[(0, 0)]
        }

        self._create_versus_graph(args.sim, graph_parameters, varying,
            custom_yaxis_range_max=custom_yaxis_range_max,
            yextractor = yextractors,
            xaxis_font = "',16'",
            yaxis_font = "',16'",
            xlabel_font = "',18'",
            ylabel_font = "',18'",
            line_width = 3,
            point_size = 1,
            nokey = True,
            generate_legend_graph = True,
            legend_font_size = 16,
        )
