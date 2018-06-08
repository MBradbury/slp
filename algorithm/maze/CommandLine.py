
import datetime
import itertools


import simulator.sim
from simulator import CommandLineCommon

import algorithm
protectionless = algorithm.import_algorithm("protectionless")
phantom_chen = algorithm.import_algorithm("phantom_chen")
lprouting_chen = algorithm.import_algorithm("ilprouting_chen")
adaptive_spr_notify_chen = algorithm.import_algorithm("adaptive_spr_notify_chen")

from data import results

from data.table import fake_result, comparison
from data.graph import summary, min_max_versus, dual_min_max_versus
from data.util import scalar_extractor

from data import submodule_loader

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super(CLI, self).__init__(protectionless.name)

        subparser = self._add_argument("table", self._run_table)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--show", action="store_true", default=False)
        
        subparser = self._add_argument("graph", self._run_graph)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")

        subparser = self._add_argument("graph-sf", self._run_graph_sf)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")

        subparser = self._add_argument("graph-min-max", self._run_min_max_versus)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")

    def _cluster_time_estimator(self, sim, args, **kwargs):
        """Estimates how long simulations are run for. Override this in algorithm
        specific CommandLine if these values are too small or too big. In general
        these have been good amounts of time to run simulations for. You might want
        to adjust the number of repeats to get the simulation time in this range."""
        size = args['network size']
        if size == 11:
            return datetime.timedelta(hours=1)
        elif size == 15:
            return datetime.timedelta(hours=2)
        elif size == 21:
            return datetime.timedelta(hours=3)
        elif size == 25:
            return datetime.timedelta(hours=4)
        else:
            raise RuntimeError("No time estimate for network sizes other than 11, 15, 21 or 25")
        
    def _argument_product(self, sim, extras=None):
        parameters = self.algorithm_module.Parameters

        argument_product = list(itertools.product(
            parameters.sizes, parameters.configurations,
            parameters.attacker_models, parameters.noise_models,
            parameters.communication_models, parameters.fault_models,
            [parameters.distance], parameters.node_id_orders, [parameters.latest_node_start_time],
            parameters.source_periods, parameters.sleep_duration, parameters.sleep_probability, 
            parameters.non_sleep_closer_to_source, parameters.non_sleep_closer_to_sink, parameters.safety_factors
        ))

        argument_product = self.add_extra_arguments(argument_product, extras)

        argument_product = self.adjust_source_period_for_multi_source(sim, argument_product)

        return argument_product

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 1.0


    def _run_table(self, args):
        parameters = [
            #'normal latency', 
            #'sent', 
            'captured',
            'received ratio',
            #'attacker distance wrt src',
            #'attacker distance',
            #'failed avoid sink',
            #'failed avoid sink when captured',
        ]

        self._create_results_table(args.sim, parameters, show=args.show)

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Message Latency (msec)', 'left top'),
            #'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            #'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'norm(sent,time taken)': ('Messages Transmission (messages)', 'left top'),
            #'norm(norm(sent,time taken),network size)': ('Messages Sent per Second per Node', 'left top'),
            #'attacker distance': ('Attacker Distance From Source (Meters)', 'left top'),
            #'failed avoid sink': ('Failed to Avoid Sink (%)', 'left top'),
            #'failed avoid sink when captured': ('Failed to Avoid Sink When Captured (%)', 'left top'),
        }

        varying = [
            #(('network size', ''), ('source period', '')),
            (('network size', ''), ('sleep probability', '')),
        ]

        custom_yaxis_range_max = {
            'captured': 80,
            'received ratio': 100,
            'normal latency': 200,
            'norm(sent,time taken)': 2000
        }

        def filter_params(all_params):
            return all_params['safety factor'] != '1.2'           

        yextractors = { }      

        self._create_versus_graph(args.sim, graph_parameters, varying,
            custom_yaxis_range_max=custom_yaxis_range_max,
            results_filter=filter_params,
            yextractor = yextractors,
            xaxis_font = "',16'",
            yaxis_font = "',16'",
            xlabel_font = "',18'",
            ylabel_font = "',16'",
            line_width = 3,
            point_size = 1,
            nokey = True,
            generate_legend_graph = True,
            legend_font_size = 16,
        )

    def _run_graph_sf(self, args):
        graph_parameters = {
            'normal latency': ('Message Latency (msec)', 'left top'),
            #'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            #'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'norm(sent,time taken)': ('Messages Transmission (messages)', 'left top'),
            #'norm(norm(sent,time taken),network size)': ('Messages Sent per Second per Node', 'left top'),
            #'attacker distance': ('Attacker Distance From Source (Meters)', 'left top'),
            #'failed avoid sink': ('Failed to Avoid Sink (%)', 'left top'),
            #'failed avoid sink when captured': ('Failed to Avoid Sink When Captured (%)', 'left top'),
        }

        varying = [
            #(('network size', ''), ('source period', '')),
            (('safety factor', ''), ('sleep probability', '')),
        ]

        custom_yaxis_range_max = {
            'captured': 100,
            'received ratio': 100,
            'normal latency': 200,
            'norm(sent,time taken)': 2000
        }          

        yextractors = { }      

        self._create_versus_graph(args.sim, graph_parameters, varying,
            custom_yaxis_range_max=custom_yaxis_range_max,
            yextractor = yextractors,
            xaxis_font = "',16'",
            yaxis_font = "',16'",
            xlabel_font = "',18'",
            ylabel_font = "',16'",
            line_width = 3,
            point_size = 1,
            nokey = True,
            generate_legend_graph = True,
            legend_font_size = 16,
        )

    def _run_min_max_versus(self, args):
        graph_parameters = {
            'normal latency': ('Message Latency (msec)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'norm(sent,time taken)': ('Messages Transmission (messages)', 'left top'),
        }

        custom_yaxis_range_max = {
            'captured': 100,
            'received ratio': 100,
            'normal latency': 3000,
            'norm(sent,time taken)': 2000
        }

        key_equivalence = {
            "attacker model": {"SeqNosReactiveAttacker()": "SeqNosOOOReactiveAttacker()"}
        }

        varying = [
            (('safety factor', ''), ('sleep probability', '')),
        ]

        args = (
            args.sim, [phantom_chen, lprouting_chen, adaptive_spr_notify_chen], None, graph_parameters, varying
        )

        kwargs = {
            "min_label": ["Phantom - Min", "ILP - Min", "AdaptiveSPR - Min"],
            "max_label": ["Phantom - Max", "ILP - Max", "AdaptiveSPR - Max"],
            "min_max_same_label": ["Phantom", "ILP", "AdaptiveSPR"],
            "vary_label": "",
            #"comparison_label": "PW",
            #"vvalue_label_converter": self.vvalue_converter,
            "key_equivalence": key_equivalence,
            "nokey": True,
            "generate_legend_graph": True,
            "custom_yaxis_range_max": custom_yaxis_range_max,
        }

        self._create_min_max_versus_graph(*args, **kwargs)