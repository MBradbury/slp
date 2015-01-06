#!/usr/bin/env python

from __future__ import print_function

import os, sys, shutil

args = []
if len(sys.argv[1:]) == 0:
    raise RuntimeError("No arguments provided!")
else:
    args = sys.argv[1:]

import algorithm.protectionless as protectionless

from data.table import safety_period, comparison, direct_comparison
from data.graph import summary, heatmap, versus
from data import results, latex

import numpy

# Raise all numpy errors
numpy.seterr(all='raise')

jar_path = 'run.py'

results_directory = 'results/protectionless'
analysis_result_file = 'protectionless-results.csv'

graphs_directory = os.path.join(results_directory, 'Graphs')

distance = 4.5

sizes = [ 11, 15, 21, 25 ]

periods = [ 1.0, 0.5, 0.25, 0.125 ]

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

repeats = 750

parameter_names = tuple()

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

create_dirtree(results_directory)
create_dirtree(graphs_directory)

if 'cluster' in args:
    cluster_directory = "cluster/protectionless"

    from data import cluster_manager

    cluster = cluster_manager.load(args)

    if 'build' in args:
        recreate_dirtree(cluster_directory)
        touch("{}/__init__.py".format(os.path.dirname(cluster_directory)))
        touch("{}/__init__.py".format(cluster_directory))

        runner = protectionless.Runner.RunSimulations(cluster.builder(), cluster_directory, False)
        runner.run(jar_path, distance, sizes, periods, configurations, repeats)

    if 'copy' in args:
        cluster.copy_to()

    if 'submit' in args:
        runner = protectionless.Runner.RunSimulations(cluster.submitter(), cluster_directory, False)
        runner.run(jar_path, distance, sizes, periods, configurations, repeats)

    if 'copy-back' in args:
        cluster.copy_back("protectionless")

    sys.exit(0)

if 'all' in args or 'run' in args:
    from data.run.driver import local as LocalDriver

    runner = protectionless.Runner.RunSimulations(LocalDriver.Runner(), results_directory)
    runner.run(jar_path, distance, sizes, periods, configurations, repeats)

if 'all' in args or 'analyse' in args:
    analyzer = protectionless.Analysis.Analyzer(results_directory)
    analyzer.run(analysis_result_file)

if 'all' in args or 'table' in args:
    safety_period_table_generator = safety_period.TableGenerator()
    safety_period_table_generator.analyse(os.path.join(results_directory, analysis_result_file))

    safety_period_table_path = 'safety_period_table.tex'

    with open(safety_period_table_path, 'w') as latex_safety_period_tables:
        latex.print_header(latex_safety_period_tables)
        safety_period_table_generator.print_table(latex_safety_period_tables)
        latex.print_footer(latex_safety_period_tables)

    latex.compile(safety_period_table_path)

analysis_result_path = os.path.join(results_directory, analysis_result_file)

if 'all' in args or 'graph' in args:
    protectionless_results = results.Results(analysis_result_path,
        parameters=parameter_names,
        results=('sent heatmap', 'received heatmap'))

    heatmap.Grapher(graphs_directory, protectionless_results, 'sent heatmap').create()
    heatmap.Grapher(graphs_directory, protectionless_results, 'received heatmap').create()

    # Don't need these as they are contained in the results file
    #for subdir in ['Collisions', 'FakeMessagesSent', 'NumPFS', 'NumTFS', 'PCCaptured', 'RcvRatio']:
    #    summary.GraphSummary(
    #        os.path.join(graphs_directory, 'Versus/{}/Source-Period'.format(subdir)),
    #        subdir).run()

    summary.GraphSummary(os.path.join(graphs_directory, 'sent heatmap'), 'protectionless-SentHeatMap').run()
    summary.GraphSummary(os.path.join(graphs_directory, 'received heatmap'), 'protectionless-ReceivedHeatMap').run()

if 'ccpe-comparison-table' in args:
    from data.old_results import OldResults 

    old_results = OldResults('results/CCPE/protectionless-results.csv',
        parameters=tuple(),
        results=('time taken', 'received ratio', 'safety period'))

    protectionless_results = results.Results(analysis_result_path,
        parameters=parameter_names,
        results=('time taken', 'received ratio', 'safety period'))

    result_table = direct_comparison.ResultTable(old_results, protectionless_results)

    def create_comparison_table(name, param_filter=lambda x: True):
        filename = name + ".tex"

        with open(filename, 'w') as result_file:
            latex.print_header(result_file)
            result_table.write_tables(result_file, param_filter)
            latex.print_footer(result_file)

        latex.compile(filename)

    create_comparison_table('protectionless-ccpe-comparison')

if 'ccpe-comparison-graph' in args:
    from data.old_results import OldResults

    result_names = ('time taken', 'received ratio', 'safety period')

    old_results = OldResults('results/CCPE/protectionless-results.csv',
        parameters=parameter_names,
        results=result_names)

    protectionless_results = results.Results(analysis_result_path,
        parameters=parameter_names,
        results=result_names)

    result_table = direct_comparison.ResultTable(old_results, protectionless_results)

    def create_ccpe_comp_versus(yxaxis, pc=False):
        name = 'ccpe-comp-{}-{}'.format(yxaxis, "pcdiff" if pc else "diff")

        versus.Grapher(graphs_directory, result_table, name,
            xaxis='size', yaxis=yxaxis, vary='source period',
            yextractor=lambda (diff, pcdiff): pcdiff if pc else diff).create()

        summary.GraphSummary(os.path.join(graphs_directory, name), 'protectionless-{}'.format(name).replace(" ", "_")).run()

    for result_name in result_names:
        create_ccpe_comp_versus(result_name, pc=True)
        create_ccpe_comp_versus(result_name, pc=False)
