
from datetime import timedelta
import itertools
import os.path

from simulator import CommandLineCommon
import simulator.sim

import algorithm
protectionless = algorithm.import_algorithm("protectionless", extras=["Analysis"])
adaptive_spr_notify = algorithm.import_algorithm("adaptive_spr_notify", extras=["Analysis"])
adaptive_spr_notify_tinyoslpl = algorithm.import_algorithm("adaptive_spr_notify_tinyoslpl", extras=["Analysis"])

from data import results, submodule_loader
from data.table import fake_result
from data.graph import summary, min_max_versus
from data.util import scalar_extractor
import data.testbed

safety_period_equivalence = {
    "low power listening": {"enabled": "disabled"}
}

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super().__init__(protectionless.name, safety_period_equivalence=safety_period_equivalence)

        subparser = self._add_argument("table", self._run_table)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--show", action="store_true", default=False)
        subparser.add_argument("--testbed", type=str, choices=submodule_loader.list_available(data.testbed), default=None, help="Select the testbed to analyse. (Only if not analysing regular results.)")
        
        subparser = self._add_argument("graph", self._run_graph)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--testbed", type=str, choices=submodule_loader.list_available(data.testbed), default=None, help="Select the testbed to analyse. (Only if not analysing regular results.)")

        subparser = self._add_argument("graph-min-max", self._run_graph_min_max)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")

        subparser = self._add_argument("graph-testbed", self._run_graph_testbed)
        subparser.add_argument("testbed", type=str, choices=submodule_loader.list_available(data.testbed), help="Select the testbed to analyse. (Only if not analysing regular results.)")

    def _argument_product(self, sim, extras=None):
        parameters = self.algorithm_module.Parameters

        parameter_values = self._get_global_parameter_values(sim, parameters)

        for parameter in self.algorithm_module.base_parameter_names:
             parameter_values.append(self._get_local_parameter_values(parameters, parameter))

        my_paramater_names = self.algorithm_module.extra_parameter_names
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
        result_file_path = self.get_results_file_path(args.sim, testbed=args.testbed)

        adaptive_results = results.Results(
            args.sim, result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=(
                'repeats',
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
            #"attacker distance percentage": ('Normalised Attacker Distance (%)', 'left top'),
            'average duty cycle': ('Average Duty Cycle (%)', 'right top'),
            'norm(norm(sent,time taken),network size)': ('Messages Sent per Sec per Node', 'left top'),
            'norm(norm(fake,time taken),network size)': ('Fake Messages Sent per Sec per Node', 'left top'),
        }

        lpl_params = self.algorithm_module.extra_parameter_names

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

            if data_key[-1] != 'enabled':
                raise RuntimeError(f"Expected 'enabled', got {data_key[-1]}")

            # adaptive_spr_notify doesn't run with lpl enabled, but that is what we want to compare against
            data_key = data_key[:-1] + ('disabled',)

            return baseline_results.data[data_key][src_period][baseline_params]

        def filter_params(all_params):
            return all_params['source period'] == '0.25'

        self._create_baseline_versus_graph(args.sim, adaptive_spr_notify, graph_parameters, varying,
            testbed=args.testbed,

            results_filter=filter_params,
            custom_yaxis_range_max=custom_yaxis_range_max,
            #custom_yaxis_range_min=custom_yaxis_range_min,
            yextractor = yextractors,
            xaxis_font = "',18'",
            yaxis_font = "',18'",
            xlabel_font = "',16'",
            ylabel_font = "',15'",
            line_width = 3,
            point_size = 1,
            nokey = True,
            generate_legend_graph = True,
            legend_font_size = 16,
            legend_divisor = 4,
            legend_base_height = 0.3,
            vary_label = "",
            baseline_label="DynamicSPR (no duty cycle)",

            fetch_baseline_result=fetch_baseline_result,
        )

    def _run_graph_min_max(self, args):
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
            #"attacker distance percentage": ('Normalised Attacker Distance (%)', 'left top'),
            'average duty cycle': ('Average Duty Cycle (%)', 'right top'),
            'norm(norm(sent,time taken),network size)': ('Messages Sent per Sec per Node', 'left top'),
            'norm(norm(fake,time taken),network size)': ('Fake Messages Sent per Sec per Node', 'left top'),
        }

        lpl_params = self.algorithm_module.extra_parameter_names

        varying = [
            #(('network size', ''), ('source period', ' seconds')),
            #(('network size', ''), (lpl_params, '~')),
            (('source period', ''), (lpl_params, '~')),
        ]

        custom_yaxis_range_max = {
            'captured': 25,
            'received ratio': 100,
            'average duty cycle': 100,
            'normal latency': 1000,
            'attacker distance': 70,
            'norm(norm(fake,time taken),network size)': 4,
            'norm(norm(sent,time taken),network size)': 5,
        }

        key_equivalence = {
            "low power listening": {"enabled": "disabled"}
        }

        #custom_yaxis_range_min = {
        #    'received ratio': 70,
        #}

        def vvalue_converter(name):
            try:
                return {
                    "PB_FIXED1_APPROACH": "Fixed1",
                    "PB_FIXED2_APPROACH": "Fixed2",
                }[name]
            except KeyError:
                return name

        yextractors = {
            # Just get the distance of attacker 0 from node 0 (the source in SourceCorner)
            "attacker distance": lambda yvalue: scalar_extractor(yvalue)[(0, 0)]
        }

        def fetch_baseline_result(baseline_results, data_key, src_period, baseline_params):

            if data_key[-1] != 'enabled':
                raise RuntimeError(f"Expected 'enabled', got {data_key[-1]}")

            # adaptive_spr_notify doesn't run with lpl enabled, but that is what we want to compare against
            data_key = data_key[:-1] + ('disabled',)

            return baseline_results.data[data_key][src_period][baseline_params]

        def filter_params(all_params):
            return all_params['source period'] == '0.25' or all_params['network size'] == '5'

        self._create_min_max_versus_graph(args.sim, [adaptive_spr_notify_tinyoslpl], adaptive_spr_notify, graph_parameters, varying,
            #testbed=args.testbed,
            vvalue_label_converter = vvalue_converter,

            results_filter=filter_params,
            custom_yaxis_range_max=custom_yaxis_range_max,
            #custom_yaxis_range_min=custom_yaxis_range_min,
            key_equivalence=key_equivalence,
            yextractor = yextractors,
            xaxis_font = "',18'",
            yaxis_font = "',18'",
            xlabel_font = "',16'",
            ylabel_font = "',15'",
            line_width = 3,
            point_size = 1,
            nokey = False,
            generate_legend_graph = True,
            legend_font_size = 16,
            legend_divisor = 4,
            legend_base_height = 0.5,
            vary_label = "",
            #baseline_label="DynamicSPR (no duty cycle)",

            max_label = ['TinyOS LPL Max'],#'DynamicSPR Max', 
            min_label = ['TinyOS LPL Min'], #'DynamicSPR Min', 
            min_max_same_label = ["TinyOS LPL"],#"DynamicSPR", 
            comparison_label = "DC",
            baseline_label = "DynamicSPR",

            #squash_path=True,

            fetch_baseline_result=fetch_baseline_result,
        )

    def _run_graph_testbed(self, args):
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
            #"attacker distance percentage": ('Normalised Attacker Distance (%)', 'left top'),
            'norm(norm(sent,time taken),network size)': ('Messages Sent per Second per Node', 'left top'),
            'norm(norm(fake,time taken),network size)': ('Fake Messages Sent per Second per node', 'left top'),
            'average power consumption': ('Average Power Consumption (mA)', 'left top'),
            'average power used': ('Average Energy Consumed (mAh)', 'left top'),
            'time taken': ('Time Taken (sec)', 'left top'),
            'average duty cycle': ('Average Duty Cycle (%)', 'right top'),
        }

        lpl_params = self.algorithm_module.extra_parameter_names

        varying = [
            #(('network size', ''), ('source period', ' seconds')),
            #(('source period', ' seconds'), ('approach', '~')),
            (('source period', ' seconds'), (lpl_params, '~')),
        ]

        custom_yaxis_range_max = {
            'received ratio': 100,
            'captured': 30,
            'norm(norm(sent,time taken),network size)': 4,
            'norm(norm(fake,time taken),network size)': 4,
            'average power consumption': 20,
            'average power used': 0.04,
            'normal latency': 300,
            'attacker distance': 600,
            'average duty cycle': 100,
        }

        def vvalue_converter(name):
            try:
                return {
                    "PB_FIXED1_APPROACH": "Fixed1",
                    "PB_FIXED2_APPROACH": "Fixed2",
                }[name]
            except KeyError:
                return name
            
        yextractors = {
            "attacker distance": lambda vvalue: scalar_extractor(vvalue)[(1, 0)]
        }

        def fetch_baseline_result(baseline_results, data_key, src_period, baseline_params):

            if data_key[-1] != 'enabled':
                raise RuntimeError(f"Expected 'enabled', got {data_key[-1]}")

            # adaptive_spr_notify doesn't run with lpl enabled, but that is what we want to compare against
            data_key = data_key[:-1] + ('disabled',)

            return baseline_results.data[data_key][src_period][baseline_params]

        def filter_params(all_params):
            return all_params['source period'] == '0.5'

        self._create_baseline_versus_graph("real", adaptive_spr_notify, graph_parameters, varying,
            custom_yaxis_range_max=custom_yaxis_range_max,
            testbed=args.testbed,
            vvalue_label_converter = vvalue_converter,
            yextractor = yextractors,
            generate_legend_graph = True,
            xaxis_font = "',16'",
            yaxis_font = "',16'",
            xlabel_font = "',14'",
            ylabel_font = "',14'",
            line_width = 3,
            point_size = 1,
            nokey = True,
            legend_divisor = 3,
            legend_font_size = '14',
            legend_base_height = 0.5,

            vary_label = "",
            baseline_label="DynamicSPR (no duty cycle)",

            fetch_baseline_result=fetch_baseline_result,

            results_filter=filter_params,
        )
