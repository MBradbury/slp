#!/usr/bin/env python

from __future__ import print_function

import os
import sys

args = []
if len(sys.argv[1:]) == 0:
    raise RuntimeError("No arguments provided!")
else:
    args = sys.argv[1:]

from data.run import protectionless as run_protectionless
from data.analysis import protectionless as analyse_protectionless

from data.run import preliminary as run_preliminary
from data.analysis import preliminary as analyse_preliminary

from data.run.driver import local as LocalDriver
from data.table import safety_period, fake_source_result, comparison
from data.graph import grapher, summary

from data.latex import latex

jar_path = 'run.py'

protectionless_results_directory = 'data/results/Protectionless'
protectionless_analysis_result_file = 'protectionless-results.csv'

preliminary_results_directory = 'data/results/Preliminary'
preliminary_analysis_result_file = 'preliminary-results.csv'

preliminary_graphs_directory = os.path.join(preliminary_results_directory, 'Graphs')

distance = 4.5

sizes = [ 11 ]#, 15, 21, 25 ]

periods = [ 1, 0.5 ]#, 0.25, 0.125 ]

configurations = [
    ('SourceCorner', 'CHOOSE'),
    ('SinkCorner', 'CHOOSE'),
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

fake_periods = [ 0.5, 0.25 ]
temp_fake_durations = [ 2 ]

prs_tfs = [ 1.0 ]
prs_pfs = [ 1.0 ]

protectionless_configurations = [(a) for (a, b) in configurations]

def create_dirtree(path):
    if not os.path.exists(path):
        os.makedirs(path) 

create_dirtree(protectionless_results_directory)
create_dirtree(preliminary_results_directory)
create_dirtree(preliminary_graphs_directory)

if 'all' in args or 'run-protectionless' in args:
    runner = run_protectionless.RunSimulations(LocalDriver.Runner(), protectionless_results_directory)
    runner.run(jar_path, sizes, periods, protectionless_configurations, 100)

if 'all' in args or 'run' in args:
    #analyzer = analyse_protectionless.Analyzer(protectionless_results_directory)
    #analyzer.run(protectionless_analysis_result_file)

    safety_period_table_generator = safety_period.TableGenerator()
    safety_period_table_generator.analyse(os.path.join(protectionless_results_directory, protectionless_analysis_result_file))

    safety_periods = safety_period_table_generator.safety_periods()

    prelim_runner = run_preliminary.RunSimulations(LocalDriver.Runner(), preliminary_results_directory, safety_periods, skip_completed_simulations=True)
    prelim_runner.run(jar_path, distance, sizes, periods, fake_periods, temp_fake_durations, prs_tfs, prs_pfs, configurations, 100)

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
