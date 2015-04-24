#!/usr/bin/env python

from __future__ import print_function

import os, sys

args = []
if len(sys.argv[1:]) == 0:
    raise RuntimeError("No arguments provided!")
else:
    args = sys.argv[1:]

import algorithm.protectionless as protectionless

from data.table import safety_period, direct_comparison
from data.graph import summary, heatmap, versus
from data import results, latex

from data.util import create_dirtree, recreate_dirtree, touch

import numpy

# Raise all numpy errors
numpy.seterr(all='raise')

jar_path = 'run.py'

distance = 4.5

sizes = [ 11, 15, 21, 25 ]

periods = [ 1.0, 0.5, 0.25, 0.125 ]

configurations = [
    #'SourceCorner',
    #'SinkCorner',
    #'FurtherSinkCorner',
    #'Generic1',
    #'Generic2',
    
    #'RingTop',
    #'RingOpposite',
    #'RingMiddle',
    
    #'CircleEdges',
    #'CircleSourceCentre',
    #'CircleSinkCentre',

    'Source2Corners',
]

repeats = 750

attacker_models = ['SeqNoReactiveAttacker', 'SeqNosReactiveAttacker']

parameter_names = tuple()

create_dirtree(protectionless.results_path)
create_dirtree(protectionless.graphs_path)

def run(driver, results_directory, skip_completed_simulations=True):
    runner = protectionless.Runner.RunSimulations(driver, results_directory, skip_completed_simulations)
    runner.run(jar_path, distance, sizes, periods, configurations, attacker_models, repeats)

if 'cluster' in args:
    cluster_directory = os.path.join("cluster", protectionless.name)

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
        cluster.copy_back("protectionless")

    sys.exit(0)

if 'run' in args:
    from data.run.driver import local as LocalDriver
    run(LocalDriver.Runner(), protectionless.results_path)

if 'analyse' in args:
    analyzer = protectionless.Analysis.Analyzer(protectionless.results_path)
    analyzer.run(protectionless.result_file)

if 'table' in args:
    safety_period_table_generator = safety_period.TableGenerator()
    safety_period_table_generator.analyse(protectionless.result_file_path)

    safety_period_table_path = 'protectionless-results.tex'

    with open(safety_period_table_path, 'w') as latex_safety_period_tables:
        latex.print_header(latex_safety_period_tables)
        safety_period_table_generator.print_table(latex_safety_period_tables)
        latex.print_footer(latex_safety_period_tables)

    latex.compile_document(safety_period_table_path)

if 'graph' in args:
    protectionless_results = results.Results(protectionless.result_file_path,
        parameters=parameter_names,
        results=('sent heatmap', 'received heatmap'))

    heatmap.Grapher(protectionless.graphs_path, protectionless_results, 'sent heatmap').create()
    heatmap.Grapher(protectionless.graphs_path, protectionless_results, 'received heatmap').create()

    # Don't need these as they are contained in the results file
    #for subdir in ['Collisions', 'FakeMessagesSent', 'NumPFS', 'NumTFS', 'PCCaptured', 'RcvRatio']:
    #    summary.GraphSummary(
    #        os.path.join(protectionless.graphs_path, 'Versus/{}/Source-Period'.format(subdir)),
    #        subdir).run()

    summary.GraphSummary(os.path.join(protectionless.graphs_path, 'sent heatmap'), 'protectionless-SentHeatMap').run()
    summary.GraphSummary(os.path.join(protectionless.graphs_path, 'received heatmap'), 'protectionless-ReceivedHeatMap').run()

if 'ccpe-comparison-table' in args:
    from data.old_results import OldResults 

    old_results = OldResults('results/CCPE/protectionless-results.csv',
        parameters=tuple(),
        results=('time taken', 'received ratio', 'safety period'))

    protectionless_results = results.Results(protectionless.result_file_path,
        parameters=parameter_names,
        results=('time taken', 'received ratio', 'safety period'))

    result_table = direct_comparison.ResultTable(old_results, protectionless_results)

    def create_comparison_table(name, param_filter=lambda x: True):
        filename = name + ".tex"

        with open(filename, 'w') as result_file:
            latex.print_header(result_file)
            result_table.write_tables(result_file, param_filter)
            latex.print_footer(result_file)

        latex.compile_document(filename)

    create_comparison_table('protectionless-ccpe-comparison')

if 'ccpe-comparison-graph' in args:
    from data.old_results import OldResults

    result_names = ('time taken', 'received ratio', 'safety period')

    old_results = OldResults('results/CCPE/protectionless-results.csv',
        parameters=parameter_names,
        results=result_names)

    protectionless_results = results.Results(protectionless.result_file_path,
        parameters=parameter_names,
        results=result_names)

    result_table = direct_comparison.ResultTable(old_results, protectionless_results)

    def create_ccpe_comp_versus(yxaxis, pc=False):
        name = 'ccpe-comp-{}-{}'.format(yxaxis, "pcdiff" if pc else "diff")

        versus.Grapher(protectionless.graphs_path, name,
            xaxis='size', yaxis=yxaxis, vary='source period',
            yextractor=lambda (diff, pcdiff): pcdiff if pc else diff).create(result_table)

        summary.GraphSummary(os.path.join(protectionless.graphs_path, name), 'protectionless-{}'.format(name).replace(" ", "_")).run()

    for result_name in result_names:
        create_ccpe_comp_versus(result_name, pc=True)
        create_ccpe_comp_versus(result_name, pc=False)
