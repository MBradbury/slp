#!/usr/bin/env python

from __future__ import print_function

import os, sys, shutil

args = []
if len(sys.argv[1:]) == 0:
    raise RuntimeError("No arguments provided!")
else:
    args = sys.argv[1:]

import algorithm.protectionless as protectionless
import algorithm.template as template
import algorithm.adaptive as adaptive

from data.table import safety_period, fake_result, comparison
from data.graph import grapher, summary

from data.latex import latex

import numpy

# Raise all numpy errors
numpy.seterr(all='raise')

jar_path = 'run.py'

protectionless_results_directory = 'data/results/protectionless'
protectionless_analysis_result_file = 'protectionless-results.csv'

template_results_directory = 'data/results/template'
template_analysis_result_file = 'template-results.csv'

adaptive_results_directory = 'data/results/adaptive'
adaptive_analysis_result_file = 'adaptive-results.csv'

adaptive_graphs_directory = os.path.join(adaptive_results_directory, 'Graphs')

distance = 4.5

sizes = [ 11, 15 ] # [ 11, 15, 21, 25 ]

source_periods = [ 1.0, 0.5, 0.25, 0.125 ]

# TODO implement algorithm override
configurations = [
    ('SourceCorner', 'CHOOSE'),
    ('SinkCorner', 'CHOOSE'),
    ('FurtherSinkCorner', 'CHOOSE'),
    #('Generic1', 'CHOOSE'),
    #('Generic2', 'CHOOSE'),
    
    #('RingTop', 'CHOOSE'),
    #('RingOpposite', 'CHOOSE'),
    #('RingMiddle', 'CHOOSE'),
    
    #('CircleEdges', 'CHOOSE'),
    #('CircleSourceCentre', 'CHOOSE'),
    #('CircleSinkCentre', 'CHOOSE'),
]

techniques = [ "NO_COL_FULL_DIST", "COL_FULL_DIST" ]

# 6 milliseconds
alpha = 0.006

receive_ratio = 0.65

repeats = 100

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

if 'cluster' in args:
    cluster_directory = "cluster/adaptive"

    from data import cluster_manager

    cluster = cluster_manager.load(args)

    if 'build' in args:
        recreate_dirtree(cluster_directory)
        touch("{}/__init__.py".format(os.path.dirname(cluster_directory)))
        touch("{}/__init__.py".format(cluster_directory))

        runner = adaptive.Runner.RunSimulations(ClusterBuilderDriver.Runner(), cluster_directory, None, False)
        runner.run(jar_path, distance, sizes, source_periods, techniques, configurations, alpha, receive_ratio, repeats)

    if 'copy' in args:
        cluster.copy_to()

    if 'submit' in args:
        safety_period_table_generator = safety_period.TableGenerator()
        safety_period_table_generator.analyse(os.path.join(protectionless_results_directory, protectionless_analysis_result_file))

        safety_periods = safety_period_table_generator.safety_periods()

        runner = adaptive.Runner.RunSimulations(cluster.submitter(), cluster_directory, safety_periods, False)
        runner.run(jar_path, distance, sizes, source_periods, techniques, configurations, alpha, receive_ratio, repeats)

    if 'copy-back' in args:
        cluster.copy_back()

    sys.exit(0)

if 'all' in args or 'run' in args:
    safety_period_table_generator = safety_period.TableGenerator()
    safety_period_table_generator.analyse(os.path.join(protectionless_results_directory, protectionless_analysis_result_file))

    safety_periods = safety_period_table_generator.safety_periods()

    from data.run.driver import local as LocalDriver

    prelim_runner = adaptive.Runner.RunSimulations(LocalDriver.Runner(), adaptive_results_directory, safety_periods, skip_completed_simulations=True)
    prelim_runner.run(jar_path, distance, sizes, source_periods, techniques, configurations, alpha, receive_ratio, repeats)

if 'all' in args or 'analyse' in args:
    prelim_analyzer = adaptive.Analysis.Analyzer(adaptive_results_directory)
    prelim_analyzer.run(adaptive_analysis_result_file)

adaptive_analysis_result_path = os.path.join(adaptive_results_directory, adaptive_analysis_result_file)

if 'all' in args or 'graph' in args:
    prelim_grapher = grapher.Grapher(adaptive_analysis_result_path, adaptive_graphs_directory)
    prelim_grapher.create_plots()
    prelim_grapher.create_graphs()

    # Don't need these as they are contained in the results file
    #for subdir in ['Collisions', 'FakeMessagesSent', 'NumPFS', 'NumTFS', 'PCCaptured', 'RcvRatio']:
    #    summary.GraphSummary(
    #        os.path.join(adaptive_graphs_directory, 'Versus/{}/Source-Period'.format(subdir)),
    #        subdir).run()

    summary.GraphSummary(os.path.join(adaptive_graphs_directory, 'HeatMap'), 'HeatMap-template').run()

if 'all' in args or 'table' in args:
    result_table = fake_result.ResultTable(adaptive_analysis_result_path,
        parameters=('technique',),
        results=('normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs'))

    with open('adaptive_results.tex', 'w') as result_file:
        latex.print_header(result_file)
        result_table.write_tables(result_file)
        latex.print_footer(result_file)

    latex.compile('adaptive_results.tex')

#if 'all' in args or 'comparison-table' in args:
#    comparison_path = 'results/3yp-adaptive-summary.csv'
#
#    result_table = comparison.ResultTable(adaptive_analysis_result_path, comparison_path)
#
#    with open('comparison_results.tex', 'w') as result_file:
#        latex.print_header(result_file)
#        result_table.write_tables(result_file)
#        latex.print_footer(result_file)
#
#    latex.compile('comparison_results.tex')
