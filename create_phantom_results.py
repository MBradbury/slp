#!/usr/bin/env python

from __future__ import print_function

import os, sys, itertools

args = []
if len(sys.argv[1:]) == 0:
    raise RuntimeError("No arguments provided!")
else:
    args = sys.argv[1:]

import algorithm.protectionless as protectionless
import algorithm.phantom as phantom

from data.table import safety_period, fake_result
from data.graph import summary, heatmap, versus

from data import results, latex

from data.util import create_dirtree, recreate_dirtree, touch, scalar_extractor

import numpy

# Raise all numpy errors
numpy.seterr(all='raise')

jar_path = 'run.py'

distance = 4.5

sizes = [ 11, 15, 21, 25 ]

source_periods = [ 1.0, 0.5, 0.25, 0.125 ]

configurations = [
    'SourceCorner',
    'SinkCorner',
    'FurtherSinkCorner',
    #'Generic1',
    #'Generic2',
    
    #'RingTop',
    #'RingOpposite',
    #'RingMiddle',
    
    #'CircleEdges',
    #'CircleSourceCentre',
    #'CircleSinkCentre',
]

walk_hop_lengths = { 11: [6, 10, 14], 15: [10, 14, 18], 21: [16, 20, 24], 25: [20, 24, 28] }
walk_retries = [ 0, 5, 10 ]

repeats = 500

parameter_names = ('walk length', 'walk retries')

create_dirtree(phantom.results_path)
create_dirtree(phantom.graphs_path)

def run(driver, results_directory, skip_completed_simulations):
    safety_period_table_generator = safety_period.TableGenerator()
    safety_period_table_generator.analyse(protectionless.result_file_path)

    safety_periods = safety_period_table_generator.safety_periods()

    runner = phantom.Runner.RunSimulations(driver, results_directory, safety_periods, skip_completed_simulations)
    runner.run(jar_path, distance, sizes, source_periods, walk_hop_lengths, walk_retries, configurations, repeats)

if 'cluster' in args:
    cluster_directory = os.path.join("cluster", phantom.name)

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
        cluster.copy_back(phantom.name)

    sys.exit(0)

if 'run' in args:
    from data.run.driver import local as LocalDriver

    run(LocalDriver.Runner(), phantom.results_path, True)

if 'analyse' in args:
    analyzer = phantom.Analysis.Analyzer(phantom.results_path)
    analyzer.run(phantom.result_file)

if 'table' in args:
    phantom_results = results.Results(phantom.result_file_path,
        parameters=parameter_names,
        results=('normal latency', 'ssd', 'captured', 'sent', 'received ratio'))

    result_table = fake_result.ResultTable(phantom_results)

    def create_phantom_table(name, param_filter=lambda x: True):
        filename = name + ".tex"

        with open(filename, 'w') as result_file:
            latex.print_header(result_file)
            result_table.write_tables(result_file, param_filter)
            latex.print_footer(result_file)

        latex.compile_document(filename)

    create_phantom_table("phantom-results")

if 'graph' in args:
    graph_parameters = {
        'normal latency': ('Normal Message Latency (seconds)', 'left top'),
        'ssd': ('Sink-Source Distance (hops)', 'left top'),
        'captured': ('Capture Ratio (%)', 'right top'),
        'sent': ('Total Messages Sent', 'left top'),
        'received ratio': ('Receive Ratio (%)', 'left bottom'),
    }

    heatmap_results = ['sent heatmap', 'received heatmap']

    phantom_results = results.Results(phantom.result_file_path,
        parameters=parameter_names,
        results=tuple(graph_parameters.keys() + heatmap_results))    

    for name in heatmap_results:
        heatmap.Grapher(phantom.graphs_path, phantom_results, name).create()
        summary.GraphSummary(os.path.join(phantom.graphs_path, name), 'phantom-' + name.replace(" ", "_")).run()

    parameters = [
        ('source period', ' seconds'),
        ('walk length', ' hops'),
        ('walk retries', '')
    ]

    for (parameter_name, parameter_unit) in parameters:
        for (yaxis, (yaxis_label, key_position)) in graph_parameters.items():
            name = '{}-v-{}'.format(yaxis.replace(" ", "_"), parameter_name.replace(" ", "-"))

            g = versus.Grapher(phantom.graphs_path, name,
                xaxis='size', yaxis=yaxis, vary=parameter_name, yextractor=scalar_extractor)

            g.xaxis_label = 'Network Size'
            g.yaxis_label = yaxis_label
            g.vary_label = parameter_name.title()
            g.vary_prefix = parameter_unit
            g.key_position = key_position

            g.create(phantom_results)

            summary.GraphSummary(os.path.join(phantom.graphs_path, name), 'phantom-' + name).run()
