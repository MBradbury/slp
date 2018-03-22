
from datetime import timedelta
import itertools
import os.path

from simulator import CommandLineCommon
import simulator.sim

import algorithm
protectionless = algorithm.import_algorithm("protectionless")
adaptive_spr_notify = algorithm.import_algorithm("adaptive_spr_notify")

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
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            #'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            #'fake': ('Fake Messages Sent', 'left top'),
            #'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            #'tfs': ('Number of TFS Created', 'left top'),
            #'pfs': ('Number of PFS Created', 'left top'),
            #'tailfs': ('Number of TailFS Created', 'left top'),
            'attacker distance': ('Attacker-Source Distance (Meters)', 'left top'),
            'average duty cycle': ('Average Duty Cycle (%)', 'right top'),
            'norm(norm(sent,time taken),network size)': ('Messages Sent per Second per Node', 'left top'),
            'norm(norm(fake,time taken),network size)': ('Fake Messages Sent per Second per node', 'left top'),
        }

        lpl_params = ('lpl normal early', 'lpl normal late', 'lpl fake early', 'lpl fake late', 'lpl choose early', 'lpl choose late')

        varying = [
            #(('network size', ''), ('source period', ' seconds')),
            #(('network size', ''), (lpl_params, '~')),
            (('source period', ''), (lpl_params, '~')),
        ]

        custom_yaxis_range_max = {
            'captured': 25,
            'received ratio': 100,
            'average duty cycle': 100,
            'normal latency': 250,
            'attacker distance': 70,
            'norm(norm(fake,time taken),network size)': 4,
            'norm(norm(sent,time taken),network size)': 5,
        }

        #custom_yaxis_range_min = {
        #    'received ratio': 70,
        #}

        yextractors = {
            # Just get the distance of attacker 0 from node 0 (the source in SourceCorner)
            "attacker distance": lambda yvalue: scalar_extractor(yvalue)[(0, 0)]
        }

        def fetch_baseline_result(baseline_results, data_key, src_period, baseline_params):

            # adaptive_spr_notify doesn't run with lpl enabled, but that is what we want to compare against
            data_key = data_key[:-1] + ('disabled',)

            return baseline_results.data[data_key][src_period][baseline_params]

        def filter_params(all_params):
            return all_params['source period'] == '0.25'

        self._create_baseline_versus_graph(args.sim, adaptive_spr_notify, graph_parameters, varying,
            results_filter=filter_params,
            custom_yaxis_range_max=custom_yaxis_range_max,
            #custom_yaxis_range_min=custom_yaxis_range_min,
            yextractor = yextractors,
            xaxis_font = "',16'",
            yaxis_font = "',16'",
            xlabel_font = "',14'",
            ylabel_font = "',14'",
            line_width = 3,
            point_size = 1,
            nokey = True,
            generate_legend_graph = True,
            legend_font_size = 16,
            legend_divisor = 4,
            legend_base_height = 0.3,
            vary_label = "",

            fetch_baseline_result=fetch_baseline_result,
        )
