#!/usr/bin/env python

from __future__ import print_function

import os, sys

args = []
if len(sys.argv[1:]) == 0:
    raise RuntimeError("No arguments provided!")
else:
    args = sys.argv[1:]

import algorithm.protectionless as protectionless
import algorithm.adaptive as adaptive
import algorithm.motion_adaptive as motion_adaptive

from data.table import safety_period, fake_result, direct_comparison
from data.graph import summary, heatmap, versus

from data import results, latex

from data.util import create_dirtree, recreate_dirtree, touch

import numpy

# Raise all numpy errors
numpy.seterr(all='raise')

jar_path = 'run.py'

distance = 4.5

sizes = [ 11, 15, 21, 25 ]

source_periods = [ 1.0, 0.5, 0.25, 0.125 ]

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

approaches = [ "TWIDDLE_APPROACH", "INTUITION_APPROACH" ]

# 6 milliseconds
alpha = 0.006

repeats = 300

parameter_names = ('approach',)

protectionless_configurations = [(a) for (a, build) in configurations]

create_dirtree(motion_adaptive.results_path)
create_dirtree(motion_adaptive.graphs_path)

def run(driver, skip_completed_simulations):
    safety_period_table_generator = safety_period.TableGenerator()
    safety_period_table_generator.analyse(protectionless.result_file_path)

    safety_periods = safety_period_table_generator.safety_periods()
    receive_ratios = safety_period_table_generator.receive_ratios()

    runner = motion_adaptive.Runner.RunSimulations(driver, cluster_directory, safety_periods, receive_ratios, skip_completed_simulations)
    runner.run(jar_path, distance, sizes, source_periods, approaches, configurations, alpha, repeats)

if 'cluster' in args:
    cluster_directory = os.path.join("cluster", motion_adaptive.name)

    from data import cluster_manager

    cluster = cluster_manager.load(args)

    if 'build' in args:
        recreate_dirtree(cluster_directory)
        touch("{}/__init__.py".format(os.path.dirname(cluster_directory)))
        touch("{}/__init__.py".format(cluster_directory))
        
        run(cluster.builder(), False)

    if 'copy' in args:
        cluster.copy_to()

    if 'submit' in args:
        run(cluster.submitter(), False)

    if 'copy-back' in args:
        cluster.copy_back("motion_adaptive")

    sys.exit(0)

if 'run' in args:
    from data.run.driver import local as LocalDriver

    run(LocalDriver.Runner(), True)

if 'analyse' in args:
    prelim_analyzer = motion_adaptive.Analysis.Analyzer(motion_adaptive.results_path)
    prelim_analyzer.run(motion_adaptive.result_file)

if 'graph' in args:
    results = results.Results(motion_adaptive.result_file_path,
        parameters=parameter_names,
        results=('captured', 'sent heatmap', 'received heatmap'))

    heatmap.Grapher(motion_adaptive.graphs_path, results, 'sent heatmap').create()
    heatmap.Grapher(motion_adaptive.graphs_path, results, 'received heatmap').create()

    # Don't need these as they are contained in the results file
    #for subdir in ['Collisions', 'FakeMessagesSent', 'NumPFS', 'NumTFS', 'PCCaptured', 'RcvRatio']:
    #    summary.GraphSummary(
    #        os.path.join(motion_adaptive.graphs_path, 'Versus/{}/Source-Period'.format(subdir)),
    #        subdir).run()

    summary.GraphSummary(os.path.join(motion_adaptive.graphs_path, 'sent heatmap'), 'motion_adaptive-SentHeatMap').run()
    summary.GraphSummary(os.path.join(motion_adaptive.graphs_path, 'received heatmap'), 'motion_adaptive-ReceivedHeatMap').run()

    versus.Grapher(motion_adaptive.graphs_path, results, 'captured-v-source-period',
        xaxis='size', yaxis='captured', vary='source period').create()

if 'table' in args:
    results = results.Results(adaptive.result_file_path,
        parameters=parameter_names,
        results=('normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs'))

    result_table = fake_result.ResultTable(results)

    def create_adaptive_table(name, param_filter=lambda x: True):
        filename = name + ".tex"

        with open(filename, 'w') as result_file:
            latex.print_header(result_file)
            result_table.write_tables(result_file, param_filter)
            latex.print_footer(result_file)

        latex.compile_document(filename)

    create_adaptive_table("motion_adaptive_results")

if 'comparison-table' in args:

    results_to_compare = ('normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs')

    adaptive_results = results.Results(adaptive.result_file_path,
        parameters=parameter_names,
        results=results_to_compare)

    motion_adaptive_results = results.Results(motion_adaptive.result_file_path,
        parameters=parameter_names,
        results=results_to_compare)

    result_table = direct_comparison.ResultTable(adaptive_results, motion_adaptive_results)

    def create_comparison_table(name, param_filter=lambda x: True):
        filename = name + ".tex"

        with open(filename, 'w') as result_file:
            latex.print_header(result_file)
            result_table.write_tables(result_file, param_filter)
            latex.print_footer(result_file)

        latex.compile_document(filename)

    create_comparison_table("comparison_adaptive_motion_adaptive_results")
