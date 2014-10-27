#!/usr/bin/env python3

import os
import sys

args = []
if len(sys.argv[1:]) == 0:
    args.append('all')
else:
    args = sys.argv[1:]

from data.run import protectionless as run_protectionless
from data.run.driver import local as LocalDriver
from data.analysis import protectionless as analyse_protectionless
from data.table import safety_period
from data.latex import latex
from data.graph import grapher, summary

jar_path = 'run.py'

results_directory = 'data/results/Protectionless'
analysis_result_file = 'protectionless-results.csv'

graphs_directory = os.path.join(results_directory, 'Graphs')

distance = 4.5

sizes = [ 11, 15, 21, 25 ]

periods = [ 1.0, 0.5, 0.25, 0.125 ]

configurations = [
    ('GRID', 'SourceCorner'),
    ('GRID', 'SinkCorner'),
    #('GRID', 'FurtherSinkCorner'),
    #('GRID', 'Generic1'),
    #('GRID', 'Generic2'),
    
    #('RING', 'RingTop'),
    #('RING', 'RingOpposite'),
    #('RING', 'RingMiddle'),
    
    #('CIRCLE', 'CircleEdges'),
    #('CIRCLE', 'CircleSourceCentre'),
    #('CIRCLE', 'CircleSinkCentre'),
]

def create_dirtree(path):
    if not os.path.exists(path):
        os.makedirs(path) 

create_dirtree(results_directory)
create_dirtree(graphs_directory)

if 'all' in args or 'run' in args:
    runner = run_protectionless.RunSimulations(LocalDriver.Runner(), results_directory)
    runner.run(jar_path, distance, sizes, periods, configurations, 1000)

if 'all' in args or 'analyse' in args:
    analyzer = analyse_protectionless.Analyzer(results_directory)
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
    grapher = grapher.Grapher(analysis_result_path, graphs_directory)
    grapher.create_plots()
    grapher.create_graphs()

    # Don't need these as they are contained in the results file
    #for subdir in ['Collisions', 'FakeMessagesSent', 'NumPFS', 'NumTFS', 'PCCaptured', 'RcvRatio']:
    #    summary.GraphSummary(
    #        os.path.join(preliminary_graphs_directory, 'Versus/{}/Source-Period'.format(subdir)),
    #        subdir).run()

    summary.GraphSummary(os.path.join(graphs_directory, 'HeatMap'), 'HeatMap-protectionless').run()
