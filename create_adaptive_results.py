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
from data.graph import summary, heatmap, versus, bar

from data import results, latex

import numpy

# Raise all numpy errors
numpy.seterr(all='raise')

jar_path = 'run.py'

protectionless_results_directory = 'results/protectionless'
protectionless_analysis_result_file = 'protectionless-results.csv'

template_results_directory = 'results/template'
template_analysis_result_file = 'template-results.csv'

adaptive_results_directory = 'results/adaptive'
adaptive_analysis_result_file = 'adaptive-results.csv'

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

    runner = adaptive.Runner.RunSimulations(driver, cluster_directory, safety_periods, receive_ratios, skip_completed_simulations)
    runner.run(jar_path, distance, sizes, source_periods, approaches, configurations, alpha, repeats)

if 'cluster' in args:
    cluster_directory = "cluster/adaptive"

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
        cluster.copy_back("adaptive")

    sys.exit(0)

if 'run' in args:
    from data.run.driver import local as LocalDriver

    run(LocalDriver.Runner(), True)

if 'analyse' in args:
    prelim_analyzer = adaptive.Analysis.Analyzer(adaptive_results_directory)
    prelim_analyzer.run(adaptive_analysis_result_file)

adaptive_analysis_result_path = os.path.join(adaptive_results_directory, adaptive_analysis_result_file)
template_analysis_result_path = os.path.join(template_results_directory, template_analysis_result_file)

if 'graph' in args:
    adaptive_results = results.Results(adaptive_analysis_result_path,
        parameters=parameter_names,
        results=('captured', 'sent heatmap', 'received heatmap'))

    heatmap.Grapher(adaptive_graphs_directory, adaptive_results, 'sent heatmap').create()
    heatmap.Grapher(adaptive_graphs_directory, adaptive_results, 'received heatmap').create()

    # Don't need these as they are contained in the results file
    #for subdir in ['Collisions', 'FakeMessagesSent', 'NumPFS', 'NumTFS', 'PCCaptured', 'RcvRatio']:
    #    summary.GraphSummary(
    #        os.path.join(adaptive_graphs_directory, 'Versus/{}/Source-Period'.format(subdir)),
    #        subdir).run()

    summary.GraphSummary(os.path.join(adaptive_graphs_directory, 'sent heatmap'), 'adaptive-SentHeatMap').run()
    summary.GraphSummary(os.path.join(adaptive_graphs_directory, 'received heatmap'), 'adaptive-ReceivedHeatMap').run()

    versus.Grapher(adaptive_graphs_directory, adaptive_results, 'captured-v-source-period',
        xaxis='size', yaxis='captured', vary='source period').create()

if 'table' in args:
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

    create_adaptive_table("adaptive-results")

if 'comparison-table' in args:
    results_to_compare = ('normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs')

    adaptive_results = results.Results(adaptive_analysis_result_path,
        parameters=parameter_names,
        results=results_to_compare)

    template_results = results.Results(template_analysis_result_path,
        parameters=('fake period', 'temp fake duration', 'pr(tfs)', 'pr(pfs)'),
        results=results_to_compare)

    result_table = comparison.ResultTable(template_results, adaptive_results)

    def create_comparison_table(name, param_filter=lambda x: True):
        filename = name + ".tex"

        with open(filename, 'w') as result_file:
            latex.print_header(result_file)
            result_table.write_tables(result_file, param_filter)
            latex.print_footer(result_file)

        latex.compile(filename)

    create_comparison_table("adaptive-template-comparison",
        lambda (fp, dur, ptfs, ppfs): ptfs not in {0.2, 0.3, 0.4})

    create_comparison_table("adaptive-template-comparison-low-prob",
        lambda (fp, dur, ptfs, ppfs): ptfs in {0.2, 0.3, 0.4})


if 'comparison-graph' in args:
    results_to_compare = ('normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs')

    adaptive_results = results.Results(adaptive_analysis_result_path,
        parameters=parameter_names,
        results=results_to_compare)

    template_results = results.Results(template_analysis_result_path,
        parameters=('fake period', 'temp fake duration', 'pr(tfs)', 'pr(pfs)'),
        results=results_to_compare)

    result_table = comparison.ResultTable(template_results, adaptive_results)

    def create_comp_bar(show, pc=False):
        name = 'template-comp-{}-{}'.format(show, "pcdiff" if pc else "diff")

        bar.DiffGrapher(adaptive_graphs_directory, result_table, name,
            shows=[show],
            extractor=lambda (diff, pcdiff): pcdiff if pc else diff).create()

        summary.GraphSummary(os.path.join(adaptive_graphs_directory, name), 'adaptive-{}'.format(name).replace(" ", "_")).run()

    for result_name in results_to_compare:
        create_comp_bar(result_name, pc=True)
        create_comp_bar(result_name, pc=False)

    def create_comp_bar_pcdiff():
        name = 'template-comp-pcdiff'

        bar.DiffGrapher(adaptive_graphs_directory, result_table, name,
            shows=results_to_compare,
            extractor=lambda (diff, pcdiff): pcdiff).create()

        summary.GraphSummary(os.path.join(adaptive_graphs_directory, name), 'adaptive-{}'.format(name).replace(" ", "_")).run()

    create_comp_bar_pcdiff()
