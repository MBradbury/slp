#!/usr/bin/env python

from __future__ import print_function

import os, sys, shutil

args = []
if len(sys.argv[1:]) == 0:
    raise RuntimeError("No arguments provided!")
else:
    args = sys.argv[1:]

import algorithm.phantom as phantom
import algorithm.protectionless as protectionless

from data.table import safety_period
from data.graph import summary, heatmap
from data import results, latex

from data.util import create_dirtree, recreate_dirtree, touch

import numpy

# Raise all numpy errors
numpy.seterr(all='raise')

jar_path = 'run.py'

analysis_result_file = 'phantom-results.csv'

graphs_directory = os.path.join(phantom.results_path, 'Graphs')

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
    analyzer.run(analysis_result_file)

if 'table' in args:
    safety_period_table_generator = safety_period.TableGenerator()
    safety_period_table_generator.analyse(os.path.join(phantom.results_path, analysis_result_file))

    safety_period_table_path = 'safety_period_table.tex'

    with open(safety_period_table_path, 'w') as latex_safety_period_tables:
        latex.print_header(latex_safety_period_tables)
        safety_period_table_generator.print_table(latex_safety_period_tables)
        latex.print_footer(latex_safety_period_tables)

    latex.compile(safety_period_table_path)

if 'graph' in args:
    phantom_results = results.Results(phantom.result_file_path,
        parameters=parameter_names,
        results=('sent heatmap', 'received heatmap'))

    heatmap.Grapher(phantom_results, 'sent heatmap', graphs_directory).create()
    heatmap.Grapher(phantom_results, 'received heatmap', graphs_directory).create()

    # Don't need these as they are contained in the results file
    #for subdir in ['Collisions', 'FakeMessagesSent', 'NumPFS', 'NumTFS', 'PCCaptured', 'RcvRatio']:
    #    summary.GraphSummary(
    #        os.path.join(graphs_directory, 'Versus/{}/Source-Period'.format(subdir)),
    #        subdir).run()

    summary.GraphSummary(os.path.join(graphs_directory, 'sent heatmap'), 'phantom-SentHeatMap').run()
    summary.GraphSummary(os.path.join(graphs_directory, 'received heatmap'), 'phantom-ReceivedHeatMap').run()
