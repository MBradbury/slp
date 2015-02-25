#!/usr/bin/env python

from __future__ import print_function

import os, sys

args = []
if len(sys.argv[1:]) == 0:
    raise RuntimeError("No arguments provided!")
else:
    args = sys.argv[1:]

import algorithm.protectionless as protectionless
import algorithm.psrc_adaptive as psrc_adaptive

from data.table import safety_period, fake_result, comparison
from data.graph import summary, heatmap, versus, bar

from data import results, latex

from data.util import create_dirtree, recreate_dirtree, touch

import numpy

# Raise all numpy errors
numpy.seterr(all='raise')

jar_path = 'run.py'

distance = 4.5

sizes = [11, 15, 21, 25]

source_periods = [1.0, 0.5, 0.25, 0.125]

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

approaches = ["PB_SINK_APPROACH", "PB_ATTACKER_EST_APPROACH"]

repeats = 300

parameter_names = ('approach',)

protectionless_configurations = [(a) for (a, build) in configurations]

create_dirtree(psrc_adaptive.results_path)
create_dirtree(psrc_adaptive.graphs_path)

def run(driver, results_directory, skip_completed_simulations):
    safety_period_table_generator = safety_period.TableGenerator()
    safety_period_table_generator.analyse(protectionless.result_file_path)

    safety_periods = safety_period_table_generator.safety_periods()

    runner = psrc_adaptive.Runner.RunSimulations(driver, results_directory, safety_periods, skip_completed_simulations)
    runner.run(jar_path, distance, sizes, source_periods, approaches, configurations, repeats)

if 'cluster' in args:
    cluster_directory = os.path.join("cluster", psrc_adaptive.name)

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
        cluster.copy_back("psrc_adaptive")

    sys.exit(0)

if 'run' in args:
    from data.run.driver import local as LocalDriver

    run(LocalDriver.Runner(), psrc_adaptive_results_directory, True)

if 'analyse' in args:
    prelim_analyzer = psrc_adaptive.Analysis.Analyzer(psrc_adaptive.results_path)
    prelim_analyzer.run(psrc_adaptive.result_file)

if 'graph' in args:
    def extract(x):
        if numpy.isscalar(x):
            return x
        else:
            (val, stddev) = x
            return val

    versus_results = ['normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs']
    heatmap_results = ['sent heatmap', 'received heatmap']

    psrc_adaptive_results = results.Results(psrc_adaptive.result_file_path,
        parameters=parameter_names,
        results=tuple(versus_results + heatmap_results))

    for name in heatmap_results:
        heatmap.Grapher(psrc_adaptive.graphs_path, psrc_adaptive_results, name).create()
        summary.GraphSummary(os.path.join(psrc_adaptive.graphs_path, name), 'psrc_adaptive-' + name.replace(" ", "_")).run()

    for yaxis in versus_results:
        name = '{}-v-source-period'.format(yaxis.replace(" ", "_"))

        versus.Grapher(psrc_adaptive.graphs_path, name,
            xaxis='size', yaxis=yaxis, vary='source period', yextractor=extract).create(psrc_adaptive_results)

        summary.GraphSummary(os.path.join(psrc_adaptive.graphs_path, name), 'psrc_adaptive-' + name).run()

if 'table' in args:
    psrc_adaptive_results = results.Results(psrc_adaptive.result_file_path,
        parameters=parameter_names,
        results=('normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs'))

    result_table = fake_result.ResultTable(psrc_adaptive_results)

    def create_psrc_adaptive_table(name, param_filter=lambda x: True):
        filename = name + ".tex"

        with open(filename, 'w') as result_file:
            latex.print_header(result_file)
            result_table.write_tables(result_file, param_filter)
            latex.print_footer(result_file)

        latex.compile_document(filename)

    create_psrc_adaptive_table("psrc_adaptive-results")

if 'time-taken-table' in args:
    psrc_adaptive_results = results.Results(psrc_adaptive.result_file_path,
        parameters=parameter_names,
        results=('wall time', 'event count'))

    result_table = fake_result.ResultTable(psrc_adaptive_results)

    def create_psrc_adaptive_table(name, param_filter=lambda x: True):
        filename = name + ".tex"

        with open(filename, 'w') as result_file:
            latex.print_header(result_file)
            result_table.write_tables(result_file, param_filter)
            latex.print_footer(result_file)

        latex.compile_document(filename)
