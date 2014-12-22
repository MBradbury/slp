#!/usr/bin/env python

from __future__ import print_function

import os, sys, shutil

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

import numpy

# Raise all numpy errors
numpy.seterr(all='raise')

jar_path = 'run.py'

protectionless_results_directory = 'results/protectionless'
protectionless_analysis_result_file = 'protectionless-results.csv'

adaptive_results_directory = 'results/adaptive'
adaptive_analysis_result_file = 'adaptive-results.csv'

motion_adaptive_results_directory = 'results/motion_adaptive'
motion_adaptive_analysis_result_file = 'motion_adaptive-results.csv'

adaptive_graphs_directory = os.path.join(adaptive_results_directory, 'Graphs')

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

def create_dirtree(path):
    if not os.path.exists(path):
        os.makedirs(path)

def recreate_dirtree(path):
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)

def touch(fname, times=None):
    with open(fname, 'a'):
        os.utime(fname, times)

create_dirtree(adaptive_results_directory)
create_dirtree(adaptive_graphs_directory)

def run(driver, skip_completed_simulations):
    safety_period_table_generator = safety_period.TableGenerator()
    safety_period_table_generator.analyse(os.path.join(protectionless_results_directory, protectionless_analysis_result_file))

    safety_periods = safety_period_table_generator.safety_periods()
    receive_ratios = safety_period_table_generator.receive_ratios()

    runner = motion_adaptive.Runner.RunSimulations(driver, cluster_directory, safety_periods, receive_ratios, skip_completed_simulations)
    runner.run(jar_path, distance, sizes, source_periods, approaches, configurations, alpha, repeats)

if 'cluster' in args:
    cluster_directory = "cluster/motion_adaptive"

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

if 'all' in args or 'run' in args:
    from data.run.driver import local as LocalDriver

    run(LocalDriver.Runner(), True)

if 'all' in args or 'analyse' in args:
    prelim_analyzer = motion_adaptive.Analysis.Analyzer(motion_adaptive_results_directory)
    prelim_analyzer.run(motion_adaptive_analysis_result_file)

adaptive_analysis_result_path = os.path.join(adaptive_results_directory, adaptive_analysis_result_file)
motion_adaptive_analysis_result_path = os.path.join(templatemotion_adaptive_results_directory, motion_adaptive_analysis_result_file)

if 'all' in args or 'graph' in args:
    adaptive_results = results.Results(motion_adaptive_analysis_result_path,
        parameters=parameter_names,
        results=('captured', 'sent heatmap', 'received heatmap'))

    heatmap.Grapher(motion_adaptive_graphs_directory, adaptive_results, 'sent heatmap').create()
    heatmap.Grapher(motion_adaptive_graphs_directory, adaptive_results, 'received heatmap').create()

    # Don't need these as they are contained in the results file
    #for subdir in ['Collisions', 'FakeMessagesSent', 'NumPFS', 'NumTFS', 'PCCaptured', 'RcvRatio']:
    #    summary.GraphSummary(
    #        os.path.join(adaptive_graphs_directory, 'Versus/{}/Source-Period'.format(subdir)),
    #        subdir).run()

    summary.GraphSummary(os.path.join(motion_adaptive_graphs_directory, 'sent heatmap'), 'motion_adaptive-SentHeatMap').run()
    summary.GraphSummary(os.path.join(motion_adaptive_graphs_directory, 'received heatmap'), 'motion_adaptive-ReceivedHeatMap').run()

    versus.Grapher(adaptive_graphs_directory, adaptive_results, 'captured-v-source-period',
        xaxis='size', yaxis='captured', vary='source period').create()

if 'all' in args or 'table' in args:
    adaptive_results = results.Results(adaptive_analysis_result_path,
        parameters=parameter_names,
        results=('normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs'))

    result_table = fake_result.ResultTable(adaptive_results)

    def create_adaptive_table(name, param_filter=lambda x: True):
        filename = name + ".tex"

        with open(filename, 'w') as result_file:
            latex.print_header(result_file)
            result_table.write_tables(result_file, param_filter)
            latex.print_footer(result_file)

        latex.compile(filename)

    create_adaptive_table("motion_adaptive_results")

if 'all' in args or 'comparison-table' in args:

    results_to_compare = ('normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs')

    adaptive_results = results.Results(adaptive_analysis_result_path,
        parameters=parameter_names,
        results=results_to_compare)

    motion_adaptive_results = results.Results(motion_adaptive_analysis_result_path,
        parameters=parameter_names,
        results=results_to_compare)

    result_table = direct_comparison.ResultTable(adaptive_results, motion_adaptive_results)

    def create_comparison_table(name, param_filter=lambda x: True):
        filename = name + ".tex"

        with open(filename, 'w') as result_file:
            latex.print_header(result_file)
            result_table.write_tables(result_file, param_filter)
            latex.print_footer(result_file)

        latex.compile(filename)

    create_comparison_table("comparison_adaptive_motion_adaptive_results")
