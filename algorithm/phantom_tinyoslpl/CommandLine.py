
import itertools
import os

import simulator.sim
from simulator import CommandLineCommon

import algorithm
protectionless = algorithm.import_algorithm("protectionless")
phantom = algorithm.import_algorithm("phantom", extras=["Analysis"])

from data import submodule_loader, results
from data.table import fake_result
from data.graph import summary, versus, min_max_versus, dual_min_max_versus
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

        # Some complexity as the walk hop length is determined by the network size
        network_size_index = sim.global_parameter_names.index('network size')
        walk_hop_length_index = len(sim.global_parameter_names)

        parameter_values = self._get_global_parameter_values(sim, parameters)
        parameter_values.append(set(itertools.chain(*parameters.walk_hop_lengths.values())))
        parameter_values.append(parameters.landmark_nodes)

        my_paramater_names = self.algorithm_module.extra_parameter_names
        my_paramater_values = [self._get_local_parameter_values(parameters, parameter) for parameter in my_paramater_names]

        argument_product = [
            x + y
            for x in itertools.product(*parameter_values)
            for y in zip(*my_paramater_values)
        ]

        # Remove incorrect combinations of walk hop lengths
        argument_product = [
            x for x in argument_product
            if x[walk_hop_length_index] in parameters.walk_hop_lengths[x[network_size_index]]
        ]

        argument_product = self.add_extra_arguments(argument_product, extras)

        # Factor in the number of sources when selecting the source period.
        # This is done so that regardless of the number of sources the overall
        # network's normal message generation rate is the same.
        argument_product = self.adjust_source_period_for_multi_source(sim, argument_product)

        return argument_product

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 2.0


    def _run_table(self, args):
        from data.table.summary_formatter import TableDataFormatter
        fmt = TableDataFormatter()

        parameters = [
            'captured',
            'received ratio',
            'paths reached end',
            'source dropped',
            #'path dropped',
            'normal latency',
            'ssd',
            'sent',
            'norm(sent,time taken)',
            'attacker distance',
        ]

        hide_parameters = []
 
        extractors = {
            # Just get the distance of attacker 0 from node 0 (the source in SourceCorner)
            "attacker distance": lambda yvalue: yvalue[(0, 0)]
        }

        self._create_results_table(args.sim, parameters,
            fmt=fmt, hide_parameters=hide_parameters, extractors=extractors,
            orientation="landscape",
            show=args.show)

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            #'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            #'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            #'tfs': ('Number of TFS Created', 'left top'),
            #'pfs': ('Number of PFS Created', 'left top'),
            #'tailfs': ('Number of TailFS Created', 'left top'),
            'attacker distance': ('Attacker-Source Distance (Meters)', 'left top'),
            #"attacker distance percentage": ('Normalised Attacker Distance (%)', 'left top'),
            'average duty cycle': ('Average Duty Cycle (%)', 'right top'),
            #'norm(norm(sent,time taken),network size)': ('Messages Sent per Sec per Node', 'left top'),
        }

        lpl_params = self.algorithm_module.extra_parameter_names

        varying = [
            #(('network size', ''), ('source period', ' seconds')),
            #(('network size', ''), (lpl_params, '~')),
            (('source period', ''), (lpl_params, '~')),
        ]

        custom_yaxis_range_max = {
            'captured': 35,
            'received ratio': 100,
            'average duty cycle': 100,
            'normal latency': 3000,
            'attacker distance': 70,
            #'norm(norm(sent,time taken),network size)': 5,
        }

        #custom_yaxis_range_min = {
        #    'received ratio': 70,
        #}

        yextractors = {
            # Just get the distance of attacker 0 from node 0 (the source in SourceCorner)
            "attacker distance": lambda yvalue: scalar_extractor(yvalue, key=(0, 0))
        }

        def fetch_baseline_result(baseline_results, data_key, src_period, baseline_params):

            if data_key[-1] != 'enabled':
                raise RuntimeError(f"Expected 'enabled', got {data_key[-1]}")

            # adaptive_spr_notify doesn't run with lpl enabled, but that is what we want to compare against
            data_key = data_key[:-1] + ('disabled',)

            return baseline_results.data[data_key][src_period][baseline_params]

        def filter_params(all_params):
            return all_params['source period'] == '0.25'

        self._create_baseline_versus_graph(args.sim, phantom, graph_parameters, varying,
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
            nokey = False,#True,
            generate_legend_graph = True,
            legend_font_size = 16,
            legend_divisor = 4,
            legend_base_height = 0.3,
            vary_label = "",
            baseline_label="Phantom (no duty cycle)",

            fetch_baseline_result=fetch_baseline_result,
        )
