from __future__ import print_function

import os, itertools, math, datetime

import numpy as np

from simulator import CommandLineCommon

import algorithm.protectionless as protectionless

from simulator import Configuration

from data import results

from data.table import safety_period, fake_result
from data.graph import summary, versus
from data.util import scalar_extractor

from data.run.common import RunSimulationsCommon

class RunSimulations(RunSimulationsCommon):
    def _get_safety_period(self, argument_names, arguments):
        time_taken = super(RunSimulations, self)._get_safety_period(argument_names, arguments)

        if time_taken is None:
            return None

        configuration_name = arguments[argument_names.index('configuration')]
        network_size = int(arguments[argument_names.index('network size')])
        distance = float(arguments[argument_names.index('distance')])

        configuration = Configuration.create_specific(configuration_name, network_size, distance)

        ssd_avg = np.mean(list(configuration.ssd(source) for source in configuration.source_ids))
        ssd_max = max(configuration.ssd(source) for source in configuration.source_ids)

        #short_random_walk_length
        s = float(arguments[argument_names.index('short walk length')])
        #long_random_walk_length
        l = float(arguments[argument_names.index('long walk length')])
        
        #################################################################
        #ONLY for m short random walk with n long_random_walk combination.
        m = 1
        n = 2

        long_length = 1.5*ssd_max + s;
        short_length = ssd_avg
        combination_length = (m * ssd_avg + n * long_length) / (m+n)
        ##################################################################

        if ssd_max > (network_size-1) * 1.5:
            return  time_taken
        else:
            #for only short random walk.
            #return time_taken

            #for only long random walk.
            #return (0.5 + l / ssd_max) * time_taken

            #for combinations.
            return (combination_length / ssd_avg) * time_taken

class CLI(CommandLineCommon.CLI):

    executable_path = 'run.py'

    distance = 4.5

    noise_models = ["meyer-heavy"]

    communication_models = ["ideal"]

    sizes = [11, 15, 21, 25]
    #sizes = [11]

    source_periods = [1.0, 0.5, 0.25, 0.125]
    #source_periods = [ 1.0 ]

    configurations = [
        #'SourceCorner',
        #'Source2CornerTop',
        #'Source3CornerTop',

        #'SinkCorner',
        #'SinkCorner2Source',
        #'SinkCorner3Source',

        #'FurtherSinkCorner',
        #'FurtherSinkCorner2Source',
        'FurtherSinkCorner3Source'

    ]

    attacker_models = ['SeqNosReactiveAttacker()']

    repeats = 1000

    local_parameter_names = ('short walk length', 'long walk length')


    def __init__(self):
        super(CLI, self).__init__(__package__)

    def _short_long_walk_lengths(self, s, c, am, nm, d, sp):
        half_ssd = int(math.floor(s/2)) + 1
        half_ssd_further = s
        ssd_further = 2*s

        # if walk_short = walk_long 
        #walk_short = list(range(2, half_ssd))
        #walk_long = list(range(2, half_ssd))

        #adaptive here.
        #walk_short = list(range(2, half_ssd))
        #walk_long = list(range(s+2, half_ssd+s))
        
        #for the Further* topology.        
        walk_short = list(range(2, half_ssd_further))
        walk_long = list(range(ssd_further+2, ssd_further+half_ssd_further))

        return list(zip(walk_short, walk_long))

    def _time_estimater(self, *args):
        """Estimates how long simulations are run for. Override this in algorithm
        specific CommandLine if these values are too small or too big. In general
        these have been good amounts of time to run simulations for. You might want
        to adjust the number of repeats to get the simulation time in this range."""
        names = self.parameter_names()
        size = args[names.index('network size')]
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

    def _execute_runner(self, driver, result_path, skip_completed_simulations=True):
        safety_period_table_generator = safety_period.TableGenerator(protectionless.result_file_path)
        time_taken = safety_period_table_generator.time_taken()

        runner = RunSimulations(driver, self.algorithm_module, result_path,
            skip_completed_simulations=skip_completed_simulations, safety_periods=time_taken)

        argument_product = itertools.product(
            self.sizes, self.configurations,
            self.attacker_models, self.noise_models, self.communication_models,
            [self.distance], self.source_periods
        )

        argument_product = [
            (s, c, am, nm, cm, d, sp, swl, lwl)

            for (s, c, am, nm, cm, d, sp) in argument_product

            for (swl, lwl) in self._short_long_walk_lengths(s, c, am, nm, d, sp)
        ]        

        argument_product = self.adjust_source_period_for_multi_source(argument_product)

        runner.run(self.executable_path, self.repeats, self.parameter_names(), argument_product, self._time_estimater)
        

    def _run_table(self, args):
        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=('normal latency', 'ssd', 'captured', 'sent', 'received ratio'))

        result_table = fake_result.ResultTable(phantom_results)

        self._create_table("{}-results".format(self.algorithm_module.name), result_table)

    def _run_graph(self, args):
        graph_parameters = {
            'normal latency': ('Normal Message Latency (seconds)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
        }

        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            source_period_normalisation="NumSources"
        )

        parameters = [
            ('source period', ' seconds'),
            ('long walk length', ' hops'),
            ('short walk length', ' hops')
        ]

        for (parameter_name, parameter_unit) in parameters:
            for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
                name = '{}-v-{}'.format(yaxis.replace(" ", "_"), parameter_name.replace(" ", "-"))

                g = versus.Grapher(
                    self.algorithm_module.graphs_path, name,
                    xaxis='network size', yaxis=yaxis, vary=parameter_name,
                    yextractor=scalar_extractor
                )

                g.xaxis_label = 'Network Size'
                g.yaxis_label = yaxis_label
                g.vary_label = parameter_name.title()
                g.vary_prefix = parameter_unit
                g.key_position = key_position

                g.create(phantom_results)

                summary.GraphSummary(
                    os.path.join(self.algorithm_module.graphs_path, name),
                    self.algorithm_module.name + '-' + name
                ).run()

    def _run_scatter_graph(self, args):
        from data.graph import scatter

        graph_parameters = {
            'normal latency': ('Normal Message Latency (seconds)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
        }

        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            source_period_normalisation="NumSources"
        )

        combine = ["short walk length", "long walk length"]

        for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():

            name = '{}-comb-{}'.format(yaxis.replace(" ", "_"), "=".join(combine).replace(" ", "-"))

            g = scatter.Grapher(
                self.algorithm_module.graphs_path, name,
                xaxis='network size', yaxis=yaxis, combine=combine,
                yextractor=scalar_extractor
            )

            g.xaxis_label = 'Network Size'
            g.yaxis_label = yaxis_label
            g.key_position = key_position

            g.create(phantom_results)

            summary.GraphSummary(
                self.algorithm_module.graphs_path,
                self.algorithm_module.name + '-' + name
            ).run()

    def _run_best_worst_average_graph(self, args):
        from data.graph import best_worst_average_versus

        graph_parameters = {
            'normal latency': ('Normal Message Latency (seconds)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
        }

        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            source_period_normalisation="NumSources"
        )

        combine = ["short walk length", "long walk length"]

        for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():

            name = '{}-bwa-{}'.format(yaxis.replace(" ", "_"), "=".join(combine).replace(" ", "-"))

            g = best_worst_average_versus.Grapher(
                self.algorithm_module.graphs_path, name,
                xaxis='network size', yaxis=yaxis, vary=combine,
                yextractor=scalar_extractor
            )

            g.xaxis_label = 'Network Size'
            g.yaxis_label = yaxis_label
            g.key_position = key_position

            g.create(phantom_results)

            summary.GraphSummary(
                self.algorithm_module.graphs_path,
                self.algorithm_module.name + '-' + name
            ).run()

    def _run_average_graph(self, args):
        import numpy as np
        from data.graph import combine_versus

        graph_parameters = {
            'normal latency': ('Normal Message Latency (seconds)', 'left top'),
            'ssd': ('Sink-Source Distance (hops)', 'left top'),
            'captured': ('Capture Ratio (%)', 'right top'),
            'sent': ('Total Messages Sent', 'left top'),
            'received ratio': ('Receive Ratio (%)', 'left bottom'),
        }

        phantom_results = results.Results(
            self.algorithm_module.result_file_path,
            parameters=self.local_parameter_names,
            results=tuple(graph_parameters.keys()),
            source_period_normalisation="NumSources"
        )

        combine = ["short walk length", "long walk length"]

        parameters = [
            ('source period', ' seconds'),
        ]

        for (parameter_name, parameter_unit) in parameters:
            for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():

                name = '{}-v-{}-i-{}'.format(
                    yaxis.replace(" ", "_"),
                    parameter_name.replace(" ", "-"),
                    "=".join(combine).replace(" ", "-")
                )

                g = combine_versus.Grapher(
                    self.algorithm_module.graphs_path, name,
                    xaxis='network size', yaxis=yaxis, vary=parameter_name, combine=combine, combine_function=np.mean,
                    yextractor=scalar_extractor
                )

                g.xaxis_label = 'Network Size'
                g.yaxis_label = yaxis_label
                g.vary_label = parameter_name.title()
                g.vary_prefix = parameter_unit
                g.key_position = key_position

                g.create(phantom_results)

                summary.GraphSummary(
                    self.algorithm_module.graphs_path,
                    self.algorithm_module.name + '-' + name
                ).run()

    def run(self, args):
        super(CLI, self).run(args)

        if 'table' in args:
            self._run_table(args)

        if 'graph' in args:
            self._run_graph(args)

        if 'average-graph' in args:
            self._run_average_graph(args)

        if 'scatter-graph' in args:
            self._run_scatter_graph(args)

        if 'best-worst-average-graph' in args:
            self._run_best_worst_average_graph(args)
