#!/usr/bin/env python

from __future__ import print_function

import os, sys

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

from data.util import create_dirtree, recreate_dirtree, touch

import numpy

# Raise all numpy errors
numpy.seterr(all='raise')

jar_path = 'run.py'

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

approaches = [ "PB_SINK_APPROACH", "PB_ATTACKER_EST_APPROACH" ]

repeats = 300

parameter_names = ('approach',)

protectionless_configurations = [(a) for (a, build) in configurations]

create_dirtree(adaptive.results_path)
create_dirtree(adaptive.graphs_path)

def run(driver, results_directory, skip_completed_simulations):
    safety_period_table_generator = safety_period.TableGenerator()
    safety_period_table_generator.analyse(protectionless.result_file_path)

    safety_periods = safety_period_table_generator.safety_periods()

    runner = adaptive.Runner.RunSimulations(driver, results_directory, safety_periods, skip_completed_simulations)
    runner.run(jar_path, distance, sizes, source_periods, approaches, configurations, repeats)

if 'cluster' in args:
    cluster_directory = os.path.join("cluster", adaptive.name)

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
        cluster.copy_back("adaptive")

    sys.exit(0)

if 'run' in args:
    from data.run.driver import local as LocalDriver

    run(LocalDriver.Runner(), adaptive_results_directory, True)

if 'analyse' in args:
    prelim_analyzer = adaptive.Analysis.Analyzer(adaptive.results_path)
    prelim_analyzer.run(adaptive.result_file)

if 'graph' in args:
    def extract(x):
        if numpy.isscalar(x):
            return x
        else:
            (val, stddev) = x
            return val

    versus_results = ['normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs']
    heatmap_results = ['sent heatmap', 'received heatmap']

    adaptive_results = results.Results(adaptive.result_file_path,
        parameters=parameter_names,
        results=tuple(versus_results + heatmap_results))

    for name in heatmap_results:
        heatmap.Grapher(adaptive.graphs_path, adaptive_results, name).create()
        summary.GraphSummary(os.path.join(adaptive.graphs_path, name), 'adaptive-' + name.replace(" ", "_")).run()

    for yaxis in versus_results:
        name = '{}-v-source-period'.format(yaxis.replace(" ", "_"))

        versus.Grapher(adaptive.graphs_path, adaptive_results, name,
            xaxis='size', yaxis=yaxis, vary='source period', yextractor=extract).create()

        summary.GraphSummary(os.path.join(adaptive.graphs_path, name), 'adaptive-' + name).run()

if 'table' in args:
    adaptive_results = results.Results(adaptive.result_file_path,
        parameters=parameter_names,
        results=('normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs'))

    result_table = fake_result.ResultTable(adaptive_results)

    def create_adaptive_table(name, param_filter=lambda x: True):
        filename = name + ".tex"

        with open(filename, 'w') as result_file:
            latex.print_header(result_file)
            result_table.write_tables(result_file, param_filter)
            latex.print_footer(result_file)

        latex.compile_document(filename)

    create_adaptive_table("adaptive-results")

if 'comparison-table' in args:
    results_to_compare = ('normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs')

    adaptive_results = results.Results(adaptive.result_file_path,
        parameters=parameter_names,
        results=results_to_compare)

    template_results = results.Results(template.result_file_path,
        parameters=('fake period', 'temp fake duration', 'pr(tfs)', 'pr(pfs)'),
        results=results_to_compare)

    result_table = comparison.ResultTable(template_results, adaptive_results)

    def create_comparison_table(name, param_filter=lambda x: True):
        filename = name + ".tex"

        with open(filename, 'w') as result_file:
            latex.print_header(result_file)
            result_table.write_tables(result_file, param_filter)
            latex.print_footer(result_file)

        latex.compile_document(filename)

    create_comparison_table("adaptive-template-comparison",
        lambda (fp, dur, ptfs, ppfs): ptfs not in {0.2, 0.3, 0.4})

    create_comparison_table("adaptive-template-comparison-low-prob",
        lambda (fp, dur, ptfs, ppfs): ptfs in {0.2, 0.3, 0.4})


if 'comparison-graph' in args:
    results_to_compare = ('normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs')

    adaptive_results = results.Results(adaptive.result_file_path,
        parameters=parameter_names,
        results=results_to_compare)

    template_results = results.Results(template.result_file_path,
        parameters=('fake period', 'temp fake duration', 'pr(tfs)', 'pr(pfs)'),
        results=results_to_compare)

    result_table = comparison.ResultTable(template_results, adaptive_results)

    def create_comp_bar(show, pc=False):
        name = 'template-comp-{}-{}'.format(show, "pcdiff" if pc else "diff")

        bar.DiffGrapher(adaptive.graphs_path, result_table, name,
            shows=[show],
            extractor=lambda (diff, pcdiff): pcdiff if pc else diff).create()

        summary.GraphSummary(os.path.join(adaptive.graphs_path, name), 'adaptive-{}'.format(name).replace(" ", "_")).run()

    for result_name in results_to_compare:
        create_comp_bar(result_name, pc=True)
        create_comp_bar(result_name, pc=False)

    def create_comp_bar_pcdiff():
        name = 'template-comp-pcdiff'

        bar.DiffGrapher(adaptive.graphs_path, result_table, name,
            shows=results_to_compare,
            extractor=lambda (diff, pcdiff): pcdiff).create()

        summary.GraphSummary(os.path.join(adaptive.graphs_path, name), 'adaptive-{}'.format(name).replace(" ", "_")).run()

    create_comp_bar_pcdiff()
