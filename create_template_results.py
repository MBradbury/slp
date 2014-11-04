#!/usr/bin/env python

from __future__ import print_function

import os, sys, itertools

args = []
if len(sys.argv[1:]) == 0:
    raise RuntimeError("No arguments provided!")
else:
    args = sys.argv[1:]

from data.run import protectionless as run_protectionless
from data.analysis import protectionless as analyse_protectionless

from data.run import template as run_template
from data.analysis import template as analyse_template

from data.run.driver import local as LocalDriver
from data.table import safety_period, fake_source_result, comparison
from data.graph import grapher, summary

from data.latex import latex

jar_path = 'run.py'

protectionless_results_directory = 'data/results/Protectionless'
protectionless_analysis_result_file = 'protectionless-results.csv'

template_results_directory = 'data/results/Template'
template_analysis_result_file = 'template-results.csv'

template_graphs_directory = os.path.join(template_results_directory, 'Graphs')

distance = 4.5

sizes = [ 11, 15, 21, 25 ]

source_periods = [ 1.0, 0.5 , 0.25, 0.125 ]
fake_periods = [ 0.5, 0.25, 0.125, 0.0625 ]

periods = [ (src, fake) for (src, fake) in itertools.product(source_periods, fake_periods) if src / 4.0 <= fake < src ]

# TODO implement algorithm override
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


temp_fake_durations = [ 2 ] # [ 1, 2, 4 ]

prs_tfs = [ 1.0 ] # [ 1.0, 0.9, 0.8 ]
prs_pfs = [ 1.0 ] # [ 1.0 ]

protectionless_configurations = [(a) for (a, b) in configurations]

def create_dirtree(path):
    if not os.path.exists(path):
        os.makedirs(path) 

create_dirtree(protectionless_results_directory)
create_dirtree(template_results_directory)
create_dirtree(template_graphs_directory)

if 'all' in args or 'run-protectionless' in args:
    runner = run_protectionless.RunSimulations(LocalDriver.Runner(), protectionless_results_directory)
    runner.run(jar_path, distance, sizes, source_periods, protectionless_configurations, 100)

if 'all' in args or 'analyse-protectionless' in args:
    analyzer = analyse_protectionless.Analyzer(protectionless_results_directory)
    analyzer.run(protectionless_analysis_result_file)

if 'all' in args or 'run' in args:
    safety_period_table_generator = safety_period.TableGenerator()
    safety_period_table_generator.analyse(os.path.join(protectionless_results_directory, protectionless_analysis_result_file))

    safety_periods = safety_period_table_generator.safety_periods()

    prelim_runner = run_template.RunSimulations(LocalDriver.Runner(), template_results_directory, safety_periods, skip_completed_simulations=True)
    prelim_runner.run(jar_path, distance, sizes, periods, temp_fake_durations, prs_tfs, prs_pfs, configurations, 100)

if 'all' in args or 'analyse' in args:
    prelim_analyzer = analyse_template.Analyzer(template_results_directory)
    prelim_analyzer.run(template_analysis_result_file)

template_analysis_result_path = os.path.join(template_results_directory, template_analysis_result_file)

if 'all' in args or 'graph' in args:
    prelim_grapher = grapher.Grapher(template_analysis_result_path, template_graphs_directory)
    prelim_grapher.create_plots()
    prelim_grapher.create_graphs()

    # Don't need these as they are contained in the results file
    #for subdir in ['Collisions', 'FakeMessagesSent', 'NumPFS', 'NumTFS', 'PCCaptured', 'RcvRatio']:
    #    summary.GraphSummary(
    #        os.path.join(template_graphs_directory, 'Versus/{}/Source-Period'.format(subdir)),
    #        subdir).run()

    summary.GraphSummary(os.path.join(template_graphs_directory, 'HeatMap'), 'HeatMap-template').run()

if 'all' in args or 'table' in args:
    result_table = fake_source_result.ResultTable(template_analysis_result_path)

    with open('results.tex', 'w') as result_file:
        latex.print_header(result_file)
        result_table.write_tables(result_file)
        latex.print_footer(result_file)

    latex.compile('results.tex')

#if 'all' in args or 'comparison-table' in args:
#    comparison_path = 'results/3yp-adaptive-summary.csv'
#
#    result_table = comparison.ResultTable(template_analysis_result_path, comparison_path)
#
#    with open('comparison_results.tex', 'w') as result_file:
#        latex.print_header(result_file)
#        result_table.write_tables(result_file)
#        latex.print_footer(result_file)
#
#    latex.compile('comparison_results.tex')
