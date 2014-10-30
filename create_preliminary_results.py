#!/usr/bin/python
from __future__ import print_function

import os
import sys

args = []
if len(sys.argv[1:]) == 0:
    args.append('all')
else:
    args = sys.argv[1:]

from run import protectionless as run_protectionless
from analysis import protectionless as analyse_protectionless

from run import preliminary as run_preliminary
from analysis import preliminary as analyse_preliminary

from run.driver import local as LocalDriver
from table import safety_period, fake_source_result, comparison
from graph import grapher, summary

from latex import latex

jar_path = 'run.py'

protectionless_results_directory = 'data/results/Protectionless'
protectionless_analysis_result_file = 'protectionless-results.csv'

preliminary_results_directory = 'data/results/Preliminary'
preliminary_analysis_result_file = 'preliminary-results.csv'

preliminary_graphs_directory = os.path.join(preliminary_results_directory, 'Graphs')

sizes = [ 11, 15, 21, 25 ]

rates = [ 1, 2, 4, 8 ]

configurations = [
    ('GRID', 'SourceCorner', 'CHOOSE'),
    ('GRID', 'SinkCorner', 'CHOOSE'),
    #('GRID', 'FurtherSinkCorner', 'CHOOSE'),
    #('GRID', 'Generic1', 'CHOOSE'),
    #('GRID', 'Generic2', 'CHOOSE'),
    
    #('RING', 'RingTop', 'CHOOSE'),
    #('RING', 'RingOpposite', 'CHOOSE'),
    #('RING', 'RingMiddle', 'CHOOSE'),
    
    #('CIRCLE', 'CircleEdges', 'CHOOSE'),
    #('CIRCLE', 'CircleSourceCentre', 'CHOOSE'),
    #('CIRCLE', 'CircleSinkCentre', 'CHOOSE'),
]

protectionless_configurations = [(a, b) for (a, b, c) in configurations]

def create_dirtree(path):
    if not os.path.exists(path):
        os.makedirs(path) 

create_dirtree(protectionless_results_directory)
create_dirtree(preliminary_results_directory)
create_dirtree(preliminary_graphs_directory)

if 'all' in args or 'run-protectionless' in args:
    runner = run_protectionless.RunSimulations(LocalDriver.Runner(), protectionless_results_directory)
    runner.run(jar_path, sizes, rates, protectionless_configurations, 1000)

if 'all' in args or 'run' in args:
    analyzer = analyse_protectionless.Analyzer(protectionless_results_directory)
    analyzer.run(protectionless_analysis_result_file)

    safety_period_table_generator = safety_period.TableGenerator()
    safety_period_table_generator.analyse(os.path.join(protectionless_results_directory, protectionless_analysis_result_file))

    safety_periods = safety_period_table_generator.safety_periods()

    prelim_runner = run_preliminary.RunSimulations(LocalDriver.Runner(), preliminary_results_directory, safety_periods, skip_completed_simulations=True)
    prelim_runner.run(jar_path, sizes, rates, configurations, 1000)

if 'all' in args or 'analyse' in args:
    prelim_analyzer = analyse_preliminary.Analyzer(preliminary_results_directory)
    prelim_analyzer.run(preliminary_analysis_result_file)

preliminary_analysis_result_path = os.path.join(preliminary_results_directory, preliminary_analysis_result_file)

if 'all' in args or 'graph' in args:
    prelim_grapher = grapher.Grapher(preliminary_analysis_result_path, preliminary_graphs_directory)
    prelim_grapher.create_plots()
    prelim_grapher.create_graphs()

    # Don't need these as they are contained in the results file
    #for subdir in ['Collisions', 'FakeMessagesSent', 'NumPFS', 'NumTFS', 'PCCaptured', 'RcvRatio']:
    #    summary.GraphSummary(
    #        os.path.join(preliminary_graphs_directory, 'Versus/{}/Source-Period'.format(subdir)),
    #        subdir).run()

    summary.GraphSummary(os.path.join(preliminary_graphs_directory, 'HeatMap'), 'HeatMap-preliminary').run()

if 'all' in args or 'table' in args:
    result_table = fake_source_result.ResultTable(preliminary_analysis_result_path)

    with open('results.tex', 'w') as result_file:
        latex.print_header(result_file)
        result_table.write_tables(result_file)
        latex.print_footer(result_file)

    latex.compile('results.tex')

if 'all' in args or 'comparison-table' in args:
    comparison_path = 'results/3yp-adaptive-summary.csv'

    result_table = comparison.ResultTable(preliminary_analysis_result_path, comparison_path)

    with open('comparison_results.tex', 'w') as result_file:
        latex.print_header(result_file)
        result_table.write_tables(result_file)
        latex.print_footer(result_file)

    latex.compile('comparison_results.tex')
