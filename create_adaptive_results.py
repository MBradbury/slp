#!/usr/bin/env python

from __future__ import print_function

import os, sys

args = []
if len(sys.argv[1:]) == 0:
    raise RuntimeError("No arguments provided!")
else:
    args = sys.argv[1:]

import algorithm.protectionless as protectionless
import algorithm.template as template
import algorithm.adaptive as adaptive

from data.table import safety_period, fake_result, comparison
from data.graph import summary, heatmap, versus, bar, min_max_versus

from data import results, latex

from data.util import create_dirtree, recreate_dirtree, touch, useful_log10, scalar_extractor

import numpy

# Raise all numpy errors
numpy.seterr(all='raise')

jar_path = 'run.py'

distance = 4.5

sizes = [11, 15, 21, 25]

source_periods = [1.0, 0.5, 0.25, 0.125]

# TODO implement algorithm override
configurations = [
    ('SourceCorner', 'CHOOSE'),
    #('SinkCorner', 'CHOOSE'),
    #('FurtherSinkCorner', 'CHOOSE'),
    #('Generic1', 'CHOOSE'),
    #('Generic2', 'CHOOSE'),

    #('RingTop', 'CHOOSE'),
    #('RingOpposite', 'CHOOSE'),
    #('RingMiddle', 'CHOOSE'),

    #('CircleEdges', 'CHOOSE'),
    #('CircleSourceCentre', 'CHOOSE'),
    #('CircleSinkCentre', 'CHOOSE'),
]

approaches = ["PB_SINK_APPROACH", "PB_ATTACKER_EST_APPROACH"]

repeats = 300

parameter_names = ('approach',)

protectionless_configurations = [(a) for (a, build) in configurations]

create_dirtree(adaptive.results_path)
create_dirtree(adaptive.graphs_path)

def run(driver, results_directory, skip_completed_simulations):
    safety_period_table_generator = safety_period.TableGenerator()
    safety_period_table_generator.analyse(protectionless.result_file_path)

    safety_periods = safety_period_table_generator.safety_periods()

    runner = adaptive.Runner.RunSimulations(driver, results_directory, safety_periods, skip_completed_simulations)
    runner.run(jar_path, distance, sizes, source_periods, approaches, configurations, repeats)

if 'cluster' in args:
    cluster_directory = os.path.join("cluster", adaptive.name)

    from data import cluster_manager

    cluster = cluster_manager.load(args)

    if 'build' in args:
        recreate_dirtree(cluster_directory)
        touch("{}/__init__.py".format(os.path.dirname(cluster_directory)))
        touch("{}/__init__.py".format(cluster_directory))

        run(cluster.builder(), cluster_directory, False)

    if 'copy' in args:
        cluster.copy_to()

    if 'submit' in args:
        run(cluster.submitter(), cluster_directory, False)

    if 'copy-back' in args:
        cluster.copy_back(adaptive.name)

    sys.exit(0)

if 'run' in args:
    from data.run.driver import local as LocalDriver

    run(LocalDriver.Runner(), adaptive.results_path, True)

if 'analyse' in args:
    prelim_analyzer = adaptive.Analysis.Analyzer(adaptive.results_path)
    prelim_analyzer.run(adaptive.result_file)

if 'graph' in args:
    graph_parameters = {
        'normal latency': ('Normal Message Latency (seconds)', 'left top'),
        'ssd': ('Sink-Source Distance (hops)', 'left top'),
        'captured': ('Capture Ratio (%)', 'left top'),
        'fake': ('Fake Messages Sent', 'left top'),
        'sent': ('Total Messages Sent', 'left top'),
        'received ratio': ('Receive Ratio (%)', 'left bottom'),
        'tfs': ('Number of TFS Created', 'left top'),
        'pfs': ('Number of PFS Created', 'left top'),
    }

    heatmap_results = ['sent heatmap', 'received heatmap']

    adaptive_results = results.Results(adaptive.result_file_path,
        parameters=parameter_names,
        results=tuple(graph_parameters.keys() + heatmap_results))    

    for name in heatmap_results:
        heatmap.Grapher(adaptive.graphs_path, adaptive_results, name).create()
        summary.GraphSummary(os.path.join(adaptive.graphs_path, name), 'adaptive-' + name.replace(" ", "_")).run()

    for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
        name = '{}-v-source-period'.format(yaxis.replace(" ", "_"))

        g = versus.Grapher(adaptive.graphs_path, name,
            xaxis='size', yaxis=yaxis, vary='source period', yextractor=scalar_extractor)

        g.xaxis_label = 'Network Size'
        g.yaxis_label = yaxis_label
        g.vary_label = 'Source Period'
        g.vary_prefix = ' seconds'
        g.key_position = key_position

        g.create(adaptive_results)

        summary.GraphSummary(os.path.join(adaptive.graphs_path, name), 'adaptive-' + name).run()

if 'table' in args:
    adaptive_results = results.Results(adaptive.result_file_path,
        parameters=parameter_names,
        results=('normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs'))

    result_table = fake_result.ResultTable(adaptive_results)

    def create_adaptive_table(name, param_filter=lambda x: True):
        filename = name + ".tex"

        with open(filename, 'w') as result_file:
            latex.print_header(result_file)
            result_table.write_tables(result_file, param_filter)
            latex.print_footer(result_file)

        latex.compile_document(filename)

    create_adaptive_table("adaptive-results")

if 'comparison-table' in args:
    results_to_compare = ('normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs')

    adaptive_results = results.Results(adaptive.result_file_path,
        parameters=parameter_names,
        results=results_to_compare)

    template_results = results.Results(template.result_file_path,
        parameters=('fake period', 'temp fake duration', 'pr(tfs)', 'pr(pfs)'),
        results=results_to_compare)

    result_table = comparison.ResultTable(template_results, adaptive_results)

    def create_comparison_table(name, param_filter=lambda x: True):
        filename = name + ".tex"

        with open(filename, 'w') as result_file:
            latex.print_header(result_file)
            result_table.write_tables(result_file, param_filter)
            latex.print_footer(result_file)

        latex.compile_document(filename)

    create_comparison_table("adaptive-template-comparison",
        lambda (fp, dur, ptfs, ppfs): ptfs not in {0.2, 0.3, 0.4})

    create_comparison_table("adaptive-template-comparison-low-prob",
        lambda (fp, dur, ptfs, ppfs): ptfs in {0.2, 0.3, 0.4})


if 'comparison-graph' in args:
    results_to_compare = ('normal latency', 'ssd', 'captured', 'sent', 'received', 'normal', 'fake', 'away', 'choose', 'received ratio', 'tfs', 'pfs')

    adaptive_results = results.Results(adaptive.result_file_path,
        parameters=parameter_names,
        results=results_to_compare)

    template_results = results.Results(template.result_file_path,
        parameters=('fake period', 'temp fake duration', 'pr(tfs)', 'pr(pfs)'),
        results=results_to_compare)

    result_table = comparison.ResultTable(template_results, adaptive_results)

    def create_comp_bar(show, pc=False):
        name = 'template-comp-{}-{}'.format(show, "pcdiff" if pc else "diff")

        bar.DiffGrapher(adaptive.graphs_path, result_table, name,
            shows=[show],
            extractor=lambda (diff, pcdiff): pcdiff if pc else diff).create()

        summary.GraphSummary(os.path.join(adaptive.graphs_path, name), 'adaptive-{}'.format(name).replace(" ", "_")).run()

    for result_name in results_to_compare:
        create_comp_bar(result_name, pc=True)
        create_comp_bar(result_name, pc=False)

    def create_comp_bar_pcdiff(pc=True, modified=lambda x: x, name_addition=None, shows=results_to_compare):
        name = 'template-comp-{}'.format("pcdiff" if pc else "diff")
        if name_addition is not None:
            name += '-{}'.format(name_addition)

        # Normalise wrt to the number of nodes in the network
        def normalisor(key_names, key_values, params, yvalue):
            size = key_values[ key_names.index('size') ]
            result = yvalue / (size * size)

            return modified(result)

        g = bar.DiffGrapher(adaptive.graphs_path, result_table, name,
            shows=shows,
            extractor=lambda (diff, pcdiff): pcdiff if pc else diff,
            normalisor=normalisor)

        g.yaxis_label = 'Percentage Difference per Node' if pc else 'Average Difference per Node'
        if name_addition is not None:
            g.yaxis_label += ' ({})'.format(name_addition)

        g.xaxis_label = 'Parameters (P_{TFS}, D_{TFS}, Pr(TFS), Pr(PFS))'

        g.create()

        summary.GraphSummary(os.path.join(adaptive.graphs_path, name), 'adaptive-{}'.format(name).replace(" ", "_")).run()

    results_to_show = ('normal', 'fake', 'away', 'choose')

    create_comp_bar_pcdiff(pc=True,  shows=results_to_show)
    create_comp_bar_pcdiff(pc=False, shows=results_to_show)
    create_comp_bar_pcdiff(pc=True,  shows=results_to_show, modified=useful_log10, name_addition='log10')

if 'min-max-versus' in args:
    graph_parameters = {
        'normal latency': ('Normal Message Latency (seconds)', 'left top'),
        'ssd': ('Sink-Source Distance (hops)', 'left top'),
        'captured': ('Capture Ratio (%)', 'right top'),
        'fake': ('Fake Messages Sent', 'left top'),
        'sent': ('Total Messages Sent', 'left top'),
        'received ratio': ('Receive Ratio (%)', 'left bottom'),
        'tfs': ('Number of TFS Created', 'left top'),
        'pfs': ('Number of PFS Created', 'left top'),
    }

    adaptive_results = results.Results(adaptive.result_file_path,
        parameters=parameter_names,
        results=graph_parameters.keys())

    template_results = results.Results(template.result_file_path,
        parameters=('fake period', 'temp fake duration', 'pr(tfs)', 'pr(pfs)'),
        results=graph_parameters.keys())

    def graph_min_max_versus(result_name):
        name = 'min-max-template-versus-{}'.format(result_name)

        g = min_max_versus.Grapher(adaptive.graphs_path, name,
            xaxis='size', yaxis=result_name, vary='approach', yextractor=scalar_extractor)

        g.xaxis_label = 'Network Size'
        g.yaxis_label = graph_parameters[result_name][0]
        g.key_position = graph_parameters[result_name][1]

        g.min_label = 'Min Template'
        g.max_label = 'Max Template'
        g.comparison_label = 'Dynamic'
        g.vary_label = ''

        g.create(template_results, adaptive_results)

        summary.GraphSummary(os.path.join(adaptive.graphs_path, name), 'adaptive-{}'.format(name).replace(" ", "_")).run()

    for result_name in graph_parameters.keys():
        graph_min_max_versus(result_name)

if 'time-taken-table' in args:
    adaptive_results = results.Results(adaptive.result_file_path,
        parameters=parameter_names,
        results=('wall time', 'event count'))

    result_table = fake_result.ResultTable(adaptive_results)

    def create_adaptive_table(name, param_filter=lambda x: True):
        filename = name + ".tex"

        with open(filename, 'w') as result_file:
            latex.print_header(result_file)
            result_table.write_tables(result_file, param_filter)
            latex.print_footer(result_file)

        latex.compile_document(filename)
