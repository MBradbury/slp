#!/usr/bin/env python

from __future__ import print_function

import os, sys, shutil, itertools, subprocess

args = []
if len(sys.argv[1:]) == 0:
    raise RuntimeError("No arguments provided!")
else:
    args = sys.argv[1:]

import algorithm.protectionless as protectionless
import algorithm.template as template

from data.run.driver import local as LocalDriver, cluster_builder as ClusterBuilderDriver, cluster_submitter as ClusterSubmitterDriver
from data.table import safety_period, fake_source_result, comparison
from data.graph import grapher, summary

from data.latex import latex

from data import cluster

jar_path = 'run.py'

protectionless_results_directory = 'data/results/protectionless'
protectionless_analysis_result_file = 'protectionless-results.csv'

template_results_directory = 'data/results/template'
template_analysis_result_file = 'template-results.csv'

template_graphs_directory = os.path.join(template_results_directory, 'Graphs')

distance = 4.5

sizes = [ 11, 15, 21, 25 ]

# Note that our simulation only has millisecond resolution,
# so periods that require a resolution greater than 0.001 will be
# truncated. An important example of this is 0.0625 which will be truncated
# to 0.062. So 0.0625 has been rounded up.
source_periods = [ 1.0, 0.5 , 0.25, 0.125 ]
fake_periods = [ 0.5, 0.25, 0.125, 0.063 ]

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

protectionless_repeats = 750
repeats = 500

protectionless_configurations = [(a) for (a, b) in configurations]

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

create_dirtree(protectionless_results_directory)
create_dirtree(template_results_directory)
create_dirtree(template_graphs_directory)

if 'cluster' in args:
    cluster_directory = "cluster/template"

    if 'all' in args or 'build' in args:
        recreate_dirtree(cluster_directory)
        touch("{}/__init__.py".format(os.path.dirname(cluster_directory)))
        touch("{}/__init__.py".format(cluster_directory))

        runner = template.Runner.RunSimulations(ClusterBuilderDriver.Runner(), cluster_directory, None, False)
        runner.run(jar_path, distance, sizes, periods, temp_fake_durations, prs_tfs, prs_pfs, configurations, repeats)

    if 'all' in args or 'copy' in args:
        username = raw_input("Enter your Caffeine username: ")
        subprocess.check_call("rsync -avz -e ssh --delete cluster {}@caffeine.dcs.warwick.ac.uk:~/slp-algorithm-tinyos".format(username), shell=True)

    if 'all' in args or 'submit' in args:
        cluster.load_module("jdk/1.7.0_07")

        safety_period_table_generator = safety_period.TableGenerator()
        safety_period_table_generator.analyse(os.path.join(protectionless_results_directory, protectionless_analysis_result_file))

        safety_periods = safety_period_table_generator.safety_periods()

        runner = template.Runner.RunSimulations(ClusterSubmitterDriver.Runner(), cluster_directory, safety_periods, False)
        runner.run(jar_path, distance, sizes, periods, temp_fake_durations, prs_tfs, prs_pfs, configurations, repeats)

    sys.exit(0)

if 'all' in args or 'run-protectionless' in args:
    runner = protectionless.Runner.RunSimulations(LocalDriver.Runner(), protectionless_results_directory)
    runner.run(jar_path, distance, sizes, source_periods, protectionless_configurations, protectionless_repeats)

if 'all' in args or 'analyse-protectionless' in args:
    analyzer = protectionless.Analysis.Analyzer(protectionless_results_directory)
    analyzer.run(protectionless_analysis_result_file)

if 'all' in args or 'run' in args:
    safety_period_table_generator = safety_period.TableGenerator()
    safety_period_table_generator.analyse(os.path.join(protectionless_results_directory, protectionless_analysis_result_file))

    safety_periods = safety_period_table_generator.safety_periods()

    prelim_runner = template.Runner.RunSimulations(LocalDriver.Runner(), template_results_directory, safety_periods, skip_completed_simulations=True)
    prelim_runner.run(jar_path, distance, sizes, periods, temp_fake_durations, prs_tfs, prs_pfs, configurations, repeats)

if 'all' in args or 'analyse' in args:
    prelim_analyzer = template.Analysis.Analyzer(template_results_directory)
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
