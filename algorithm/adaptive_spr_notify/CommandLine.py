from __future__ import print_function

from datetime import timedelta
import os.path

from simulator import CommandLineCommon
import simulator.sim

import algorithm
protectionless = algorithm.import_algorithm("protectionless", extras=["Analysis"])
adaptive = algorithm.import_algorithm("adaptive")
template = algorithm.import_algorithm("template")
ilprouting = algorithm.import_algorithm("ilprouting")

from data import results, submodule_loader
from data.table import fake_result
from data.graph import summary, min_max_versus
from data.util import scalar_extractor
import data.testbed

class CLI(CommandLineCommon.CLI):
    def __init__(self):
        super().__init__(protectionless.name)

        subparser = self._add_argument("table", self._run_table)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")
        subparser.add_argument("--show", action="store_true", default=False)
        subparser.add_argument("--testbed", type=str, choices=submodule_loader.list_available(data.testbed), default=None, help="Select the testbed to analyse. (Only if not analysing regular results.)")
        
        subparser = self._add_argument("graph", self._run_graph)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")

        subparser = self._add_argument("graph-testbed", self._run_graph_testbed)
        subparser.add_argument("testbed", type=str, choices=submodule_loader.list_available(data.testbed), help="Select the testbed to analyse. (Only if not analysing regular results.)")

        subparser = self._add_argument("min-max-versus", self._run_min_max_versus)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")

        subparser = self._add_argument("min-max-ilp-versus", self._run_min_max_ilp_versus)
        subparser.add_argument("sim", choices=submodule_loader.list_available(simulator.sim), help="The simulator you wish to run with.")

    def time_after_first_normal_to_safety_period(self, tafn):
        return tafn * 2.0

    def _cluster_time_estimator(self, sim, args, **kwargs):
        historical_key_names = ('network size', 'source period')

        if sim == "tossim":
            # Using the historical values from AdaptiveSPR
            # Using size 11 network's time for size 7
            historical = {
                (7, 0.125): timedelta(seconds=4),
                (7, 0.25): timedelta(seconds=5),
                (7, 0.5): timedelta(seconds=6),
                (7, 1.0): timedelta(seconds=6),
                (7, 2.0): timedelta(seconds=7),
                (11, 0.125): timedelta(seconds=4),
                (11, 0.25): timedelta(seconds=5),
                (11, 0.5): timedelta(seconds=6),
                (11, 1.0): timedelta(seconds=6),
                (11, 2.0): timedelta(seconds=7),
                (15, 0.125): timedelta(seconds=20),
                (15, 0.25): timedelta(seconds=19),
                (15, 0.5): timedelta(seconds=21),
                (15, 1.0): timedelta(seconds=22),
                (15, 2.0): timedelta(seconds=27),
                (21, 0.125): timedelta(seconds=131),
                (21, 0.25): timedelta(seconds=108),
                (21, 0.5): timedelta(seconds=127),
                (21, 1.0): timedelta(seconds=114),
                (21, 2.0): timedelta(seconds=126),
                (25, 0.125): timedelta(seconds=367),
                (25, 0.25): timedelta(seconds=341),
                (25, 0.5): timedelta(seconds=307),
                (25, 1.0): timedelta(seconds=339),
                (25, 2.0): timedelta(seconds=356),
            }
        else:
            historical = {}

        return self._cluster_time_estimator_from_historical(
            sim, args, kwargs, historical_key_names, historical,
            allowance=0.3,
            max_time=timedelta(days=2)
        )



    def _run_table(self, args):
        result_file_path = self.get_results_file_path(args.sim, testbed=args.testbed)

        adaptive_results = results.Results(
            args.sim, result_file_path,
            parameters=self.algorithm_module.local_parameter_names,
            results=(
                'repeats',
                #'sent', 'delivered',
                'norm(norm(fake,time taken),network size)',
                'time taken',
                'normal latency', 'ssd', 'captured',
                'fake', 'received ratio', 
                'attacker distance',
                #'tfs', 'pfs',
                #'norm(sent,time taken)', 'norm(norm(sent,time taken),network size)',
                #'norm(norm(norm(sent,time taken),network size),source rate)'
            ))

        result_table = fake_result.ResultTable(adaptive_results)

        self._create_table(self.algorithm_module.name + "-results", result_table, show=args.show)

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'left top'),
            'fake': ('Fake Messages Sent', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'tfs': ('Number of TFS Created', 'left top'),
            'pfs': ('Number of PFS Created', 'left top'),
            'tailfs': ('Number of TailFS Created', 'left top'),
            'attacker distance': ('Attacker-Source Distance (Meters)', 'left top'),
        }

        varying = [
            (('network size', ''), ('source period', ' seconds')),
            #(('network size', ''), ('communication model', '~')),
        ]

        custom_yaxis_range_max = {
            'received ratio': 100,
        }

        self._create_versus_graph(args.sim, graph_parameters, varying,
            custom_yaxis_range_max=custom_yaxis_range_max,
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
            'norm(norm(sent,time taken),network size)': ('Messages Sent per Second per Node', 'left top'),
            'norm(norm(fake,time taken),network size)': ('Fake Messages Sent per Second per node', 'left top'),
            'average power consumption': ('Average Power Consumption (mA)', 'left top'),
            'average power used': ('Average Power Used (mAh)', 'left top'),
            'norm(average power used,time taken)': ('Normalised Average Power Used (mAh)', 'left top'),
            'time taken': ('Time Taken (sec)', 'left top'),
        }

        varying = [
            #(('network size', ''), ('source period', ' seconds')),
            (('source period', ' seconds'), ('approach', '~')),
        ]

        custom_yaxis_range_max = {
            'received ratio': 100,
            'captured': 20,
            'norm(norm(sent,time taken),network size)': 6,
            'norm(norm(fake,time taken),network size)': 6,
            'average power used': 0.035,
            'average power consumption': 20,
        }

        def vvalue_converter(name):
            try:
                return {
                    "PB_FIXED1_APPROACH": "Fixed1",
                    "PB_FIXED2_APPROACH": "Fixed2",
                    "PB_RND_APPROACH": "Rnd",
                }[name]
            except KeyError:
                return name
            
        yextractors = {
            "attacker distance": lambda vvalue: scalar_extractor(vvalue)[(1, 0)]
        }

        def filter_params(all_params):
            return all_params['source period'] == '0.5'

        self._create_baseline_versus_graph("real", protectionless, graph_parameters, varying,
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
            legend_divisor = 2,
            legend_font_size = '14',
            legend_base_height = 0.5,

            vary_label = "",
            baseline_label="Protectionless",

            results_filter=filter_params,
        )


    def _run_min_max_versus(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
#            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
#            'normal': ('Normal Messages Sent', 'left top'),
            'fake': ('Fake Messages Sent', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
#            'tfs': ('Number of TFS Created', 'left top'),
#            'pfs': ('Number of PFS Created', 'left top'),
            'attacker distance': ('Attacker-Source Distance (meters)', 'left top'),
            #'norm(sent,time taken)': ('Messages Sent per Second', 'left top'),
            #'norm(fake,time taken)': ('Messages Sent per Second', 'left top'),
            'norm(norm(sent,time taken),network size)': ('Messages Sent per Second per Node', 'left top'),
            'norm(norm(fake,time taken),network size)': ('Fake Messages Sent per Second per node', 'left top'),
#            'norm(normal,time taken)': ('Messages Sent per Second', 'left top'),
#            'norm(norm(fake,time taken),source rate)': ('~', 'left top'),
        }

        custom_yaxis_range_max = {
            'captured': 15,
            'received ratio': 100,
            'attacker distance': 160,
            'normal latency': 120,
            'norm(norm(sent,time taken),network size)': 15,
            'norm(norm(fake,time taken),network size)': 15,
        }

        def filter_params(all_params):
            return (all_params['source period'] == '0.125' or
                    all_params['noise model'] == 'meyer-heavy' or
                    all_params['configuration'] != 'SourceCorner')

        def adaptive_filter_params(all_params):
            return filter_params(all_params) or all_params['approach'] in {"PB_SINK_APPROACH", "PB_ATTACKER_EST_APPROACH"}

        protectionless_analysis = protectionless.Analysis.Analyzer(args.sim, protectionless.results_path(args.sim))

        protectionless_results = results.Results(
            args.sim, protectionless.result_file_path(args.sim),
            parameters=protectionless.local_parameter_names,
            results=list(set(graph_parameters.keys()) & set(protectionless_analysis.results_header().keys())),
            results_filter=filter_params)

        adaptive_spr_notify_results = results.Results(
            args.sim, self.algorithm_module.result_file_path(args.sim),
            parameters=self.algorithm_module.local_parameter_names,
            results=graph_parameters.keys(),
            results_filter=filter_params)

        adaptive_results = results.Results(
            args.sim, adaptive.result_file_path(args.sim),
            parameters=adaptive.local_parameter_names,
            results=graph_parameters.keys(),
            results_filter=adaptive_filter_params)

        template_results = results.Results(
            args.sim, template.result_file_path(args.sim),
            parameters=template.local_parameter_names,
            results=graph_parameters.keys(),
            results_filter=filter_params)

        def graph_min_max_versus(result_name, xaxis):
            name = 'min-max-{}-versus-{}-{}'.format(adaptive.name, result_name, xaxis)

            if result_name == "attacker distance":
                # Just get the distance of attacker 0 from node 0 (the source in SourceCorner)
                def yextractor(yvalue):
                    print(yvalue)
                    return scalar_extractor(yvalue)[(0, 0)]
            else:
                yextractor = scalar_extractor

            g = min_max_versus.Grapher(
                args.sim, self.algorithm_module.graphs_path(args.sim), name,
                xaxis=xaxis, yaxis=result_name, vary='approach', yextractor=yextractor)

            g.xaxis_label = xaxis.title()
            g.yaxis_label = graph_parameters[result_name][0]
            g.key_position = graph_parameters[result_name][1]

            g.xaxis_font = "',16'"
            g.yaxis_font = "',16'"
            g.xlabel_font = "',14'"
            g.ylabel_font = "',14'"
            g.line_width = 3
            g.point_size = 1
            g.nokey = True
            g.legend_font_size = 16

            g.min_label = ['Static - Lowest']
            g.max_label = ['Static - Highest']
            g.comparison_label = ['Dynamic', 'DynamicSpr']
            g.vary_label = ''

            if xaxis == 'network size':
                g.xvalues_to_tic_label = lambda x: f'"{x}x{x}"'

            if result_name in custom_yaxis_range_max:
                g.yaxis_range_max = custom_yaxis_range_max[result_name]

            def vvalue_converter(name):
                try:
                    return {
                        "PB_FIXED1_APPROACH": "Fixed1",
                        "PB_FIXED2_APPROACH": "Fixed2",
                        "PB_RND_APPROACH": "Rnd",
                    }[name]
                except KeyError:
                    return name
            g.vvalue_label_converter = vvalue_converter

            g.generate_legend_graph = True

            if result_name in protectionless_results.result_names:
                g.create([template_results], [adaptive_results, adaptive_spr_notify_results], baseline_results=protectionless_results)
            else:
                g.create([template_results], [adaptive_results, adaptive_spr_notify_results])

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path(args.sim), name),
                os.path.join(algorithm.results_directory_name, '{}-{}'.format(self.algorithm_module.name, name).replace(" ", "_"))
            ).run()

        for result_name in graph_parameters.keys():
            graph_min_max_versus(result_name, 'network size')



    def _run_min_max_ilp_versus(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (ms)', 'left top'),
#            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
#            'normal': ('Normal Messages Sent', 'left top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
            'attacker distance': ('Attacker-Source Distance (meters)', 'left top'),
            'norm(sent,time taken)': ('Messages Sent per Second', 'left top'),
#            'norm(norm(sent,time taken),network size)': ('Messages Sent per Second per Node', 'left top'),
#            'norm(normal,time taken)': ('Messages Sent per Second', 'left top'),
        }

        custom_yaxis_range_max = {
            'captured': 25,
            'received ratio': 100,
            'attacker distance': 120,
            'normal latency': 4000,
            'norm(sent,time taken)': 8000,
            'norm(norm(sent,time taken),network size)': 15,
        }

        def filter_params(all_params):
            return (all_params['source period'] == '0.125' or
                    all_params['noise model'] == 'meyer-heavy' or
                    all_params['configuration'] != 'SourceCorner')

        def adaptive_filter_params(all_params):
            return filter_params(all_params) or all_params['approach'] in {"PB_SINK_APPROACH", "PB_ATTACKER_EST_APPROACH"}

        def ilprouting_filter_params(all_params):
            return filter_params(all_params) or all_params["pr direct to sink"] != "0.2"

        protectionless_analysis = protectionless.Analysis.Analyzer(args.sim, protectionless.results_path(args.sim))

        protectionless_results = results.Results(
            args.sim, protectionless.result_file_path(args.sim),
            parameters=protectionless.local_parameter_names,
            results=list(set(graph_parameters.keys()) & set(protectionless_analysis.results_header().keys())),
            results_filter=filter_params)

        adaptive_spr_notify_results = results.Results(
            args.sim, self.algorithm_module.result_file_path(args.sim),
            parameters=self.algorithm_module.local_parameter_names,
            results=graph_parameters.keys(),
            results_filter=filter_params)

        adaptive_results = results.Results(
            args.sim, adaptive.result_file_path(args.sim),
            parameters=adaptive.local_parameter_names,
            results=graph_parameters.keys(),
            results_filter=adaptive_filter_params)

        ilprouting_results = results.Results(
            args.sim, ilprouting.result_file_path(args.sim),
            parameters=ilprouting.local_parameter_names,
            results=graph_parameters.keys(),
            results_filter=ilprouting_filter_params)

        sim = submodule_loader.load(simulator.sim, args.sim)

        def graph_min_max_versus(result_name, xaxis):
            name = 'min-max-ilp-versus-{}-{}'.format(result_name, xaxis)

            if result_name == "attacker distance":
                # Just get the distance of attacker 0 from node 0 (the source in SourceCorner)
                def yextractor(yvalue):
                    print(yvalue)
                    return scalar_extractor(yvalue)[(0, 0)]
            else:
                yextractor = scalar_extractor

            vary = ['approach', 'approach', ('buffer size', 'max walk length', 'pr direct to sink', 'msg group size')]

            g = min_max_versus.Grapher(
                args.sim, self.algorithm_module.graphs_path(args.sim), name,
                xaxis=xaxis, yaxis=result_name, vary=vary, yextractor=yextractor)

            g.xaxis_label = xaxis.title()
            g.yaxis_label = graph_parameters[result_name][0]
            g.key_position = graph_parameters[result_name][1]

            g.xaxis_font = "',16'"
            g.yaxis_font = "',16'"
            g.xlabel_font = "',14'"
            g.ylabel_font = "',14'"
            g.line_width = 3
            g.point_size = 1
            g.nokey = True
            g.legend_font_size = 16

            #g.min_label = ['Static - Lowest']
            #g.max_label = ['Static - Highest']
            g.comparison_label = ['Dynamic', 'DynamicSpr', 'ILPRouting']
            g.vary_label = ''

            if xaxis == 'network size':
                g.xvalues_to_tic_label = lambda x: f'"{x}x{x}"'

            if result_name in custom_yaxis_range_max:
                g.yaxis_range_max = custom_yaxis_range_max[result_name]

            def vvalue_converter(name):
                if isinstance(name, tuple):
                    (buffer_size, max_walk_length, pr_direct_to_sink, msg_group_size) = name

                    return f"Group Size {msg_group_size}"

                try:
                    return {
                        "PB_FIXED1_APPROACH": "Fixed1",
                        "PB_FIXED2_APPROACH": "Fixed2",
                        "PB_RND_APPROACH": "Rnd",
                    }[name]
                except KeyError:
                    return name
            g.vvalue_label_converter = vvalue_converter

            # Want to pretend SeqNosOOOReactiveAttacker is SeqNosReactiveAttacker
            def correct_data_key(data_key):
                data_key = list(data_key)
                data_key[sim.global_parameter_names.index('attacker model')] = "SeqNosReactiveAttacker()"
                return tuple(data_key)
            g.correct_data_key = correct_data_key

            g.generate_legend_graph = True

            if result_name in protectionless_results.result_names:
                g.create([], [adaptive_results, adaptive_spr_notify_results, ilprouting_results], baseline_results=protectionless_results)
            else:
                g.create([], [adaptive_results, adaptive_spr_notify_results, ilprouting_results])

            summary.GraphSummary(
                os.path.join(self.algorithm_module.graphs_path(args.sim), name),
                os.path.join(algorithm.results_directory_name, '{}-{}'.format(self.algorithm_module.name, name).replace(" ", "_"))
            ).run()

        for result_name in graph_parameters.keys():
            graph_min_max_versus(result_name, 'network size')
