#!/usr/bin/env python

from __future__ import print_function

import os, sys

args = []
if len(sys.argv[1:]) == 0:
    raise RuntimeError("No arguments provided!")
else:
    args = sys.argv[1:]

import algorithm.protectionless as protectionless
import algorithm.phantom as phantom

from data.table import safety_period
from data.graph import summary, heatmap

from data import results, latex

from data.util import create_dirtree, recreate_dirtree, touch

import numpy

# Raise all numpy errors
numpy.seterr(all='raise')

jar_path = 'run.py'

distance = 4.5

sizes = [ 11 ]

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

walk_hop_lengths = [ 3, 5, 7 ]

repeats = 20

parameter_names = tuple()

create_dirtree(phantom.results_path)
create_dirtree(phantom.graphs_path)

def run(driver, results_directory, skip_completed_simulations):
    safety_period_table_generator = safety_period.TableGenerator()
    safety_period_table_generator.analyse(protectionless.result_file_path)

    safety_periods = safety_period_table_generator.safety_periods()

    runner = phantom.Runner.RunSimulations(driver, results_directory, safety_periods, skip_completed_simulations)
    runner.run(jar_path, distance, sizes, source_periods, walk_hop_lengths, configurations, repeats)

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
        cluster.copy_back("phantom")

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
    phantom_results = results.Results(phantom.result_file_path,
        parameters=parameter_names,
        results=('sent heatmap', 'received heatmap'))

    heatmap.Grapher(phantom_results, 'sent heatmap', phantom.graphs_path).create()
    heatmap.Grapher(phantom_results, 'received heatmap', phantom.graphs_path).create()

    # Don't need these as they are contained in the results file
    #for subdir in ['Collisions', 'FakeMessagesSent', 'NumPFS', 'NumTFS', 'PCCaptured', 'RcvRatio']:
    #    summary.GraphSummary(
    #        os.path.join(phantom.graphs_path, 'Versus/{}/Source-Period'.format(subdir)),
    #        subdir).run()

    summary.GraphSummary(os.path.join(phantom.graphs_path, 'sent heatmap'), 'phantom-SentHeatMap').run()
    summary.GraphSummary(os.path.join(phantom.graphs_path, 'received heatmap'), 'phantom-ReceivedHeatMap').run()
