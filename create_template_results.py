#!/usr/bin/env python

from __future__ import print_function

import os, sys, itertools

args = []
if len(sys.argv[1:]) == 0:
    raise RuntimeError("No arguments provided!")
else:
    args = sys.argv[1:]

import algorithm.protectionless as protectionless
import algorithm.template as template

from data.table import safety_period, fake_result, direct_comparison
from data.graph import summary, heatmap, versus, bar
from data import results, latex

from data.util import create_dirtree, recreate_dirtree, touch

import numpy

# Raise all numpy errors
numpy.seterr(all='raise')

jar_path = 'run.py'

distance = 4.5

sizes = [ 11, 15, 21, 25 ]

# Note that our simulation only has millisecond resolution,
# so periods that require a resolution greater than 0.001 will be
# truncated. An important example of this is 0.0625 which will be truncated
# to 0.062. So 0.0625 has been rounded up.
source_periods = [ 1.0, 0.5, 0.25, 0.125 ]
fake_periods = [ 0.5, 0.25, 0.125, 0.063 ]

periods = [ (src, fake) for (src, fake) in itertools.product(source_periods, fake_periods) if src / 4.0 <= fake < src ]

# TODO implement algorithm override
configurations = [
    ('SourceCorner', 'CHOOSE'),
    ('SinkCorner', 'CHOOSE'),
    ('FurtherSinkCorner', 'CHOOSE'),
    #('Generic1', 'CHOOSE'),
    #('Generic2', 'CHOOSE'),
    
    #('RingTop', 'CHOOSE'),
    #('RingOpposite', 'CHOOSE'),
    #('RingMiddle', 'CHOOSE'),
    
    #('CircleEdges', 'CHOOSE'),
    #('CircleSourceCentre', 'CHOOSE'),
    #('CircleSinkCentre', 'CHOOSE'),
]


temp_fake_durations = [ 1, 2, 4 ]

prs_tfs = [ 1.0, 0.9, 0.8 ]
prs_pfs = [ 1.0 ]

protectionless_repeats = 750
repeats = 500

protectionless_configurations = [(a) for (a, b) in configurations]

parameter_names = ('fake period', 'temp fake duration', 'pr(tfs)', 'pr(pfs)')

create_dirtree(template.results_path)
create_dirtree(template.graphs_path)

if 'cluster' in args:
    cluster_directory = os.path.join("cluster", template.name)

    from data import cluster_manager

    cluster = cluster_manager.load(args)

    if 'build' in args:
        recreate_dirtree(cluster_directory)
        touch("{}/__init__.py".format(os.path.dirname(cluster_directory)))
        touch("{}/__init__.py".format(cluster_directory))

        runner = template.Runner.RunSimulations(cluster.builder(), cluster_directory, None, False)
        runner.run(jar_path, distance, sizes, periods, temp_fake_durations, prs_tfs, prs_pfs, configurations, repeats)

    if 'copy' in args:
        cluster.copy_to()

    if 'submit' in args:
        safety_period_table_generator = safety_period.TableGenerator()
        safety_period_table_generator.analyse(protectionless.result_file_path)

        safety_periods = safety_period_table_generator.safety_periods()

        runner = template.Runner.RunSimulations(cluster.submitter(), cluster_directory, safety_periods, False)
        runner.run(jar_path, distance, sizes, periods, temp_fake_durations, prs_tfs, prs_pfs, configurations, repeats)

    if 'copy-back' in args:
        cluster.copy_back(template.name)

    sys.exit(0)

if 'run' in args:
    safety_period_table_generator = safety_period.TableGenerator()
    safety_period_table_generator.analyse(protectionless.result_file_path)

    safety_periods = safety_period_table_generator.safety_periods()

    from data.run.driver import local as LocalDriver

    prelim_runner = template.Runner.RunSimulations(LocalDriver.Runner(), template.results_path, safety_periods, skip_completed_simulations=True)
    prelim_runner.run(jar_path, distance, sizes, periods, temp_fake_durations, prs_tfs, prs_pfs, configurations, repeats)

if 'analyse' in args:
    prelim_analyzer = template.Analysis.Analyzer(template.results_path)
    prelim_analyzer.run(template.result_file)

if 'graph' in args:
    def extract(x):
        if numpy.isscalar(x):
            return x
        else:
            (val, stddev) = x
            return val

    versus_results = ['normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs']
    heatmap_results = ['sent heatmap', 'received heatmap']

    template_results = results.Results(template.result_file_path,
        parameters=parameter_names,
        results=tuple(versus_results + heatmap_results))

    for name in heatmap_results:
        heatmap.Grapher(template.graphs_path, template_results, name).create()
        summary.GraphSummary(os.path.join(template.graphs_path, name), 'template-' + name.replace(" ", "_")).run()

    #for yaxis in versus_results:
    #    name = '{}-v-fake-period'.format(yaxis.replace(" ", "_"))
    #
    #    versus.Grapher(template.graphs_path, template_results, name,
    #        xaxis='size', yaxis=yaxis, vary='fake period', yextractor=extract).create()
    #
    #    summary.GraphSummary(os.path.join(template.graphs_path, name), 'template-' + name).run()


if 'all' in args or 'table' in args:
    template_results = results.Results(template.result_file_path,
        parameters=parameter_names,
        results=('normal latency', 'ssd', 'captured', 'fake', 'received ratio', 'tfs', 'pfs'))

    result_table = fake_result.ResultTable(template_results)

    def create_template_table(name, param_filter):
        filename = name + ".tex"

        with open(filename, 'w') as result_file:
            latex.print_header(result_file)
            result_table.write_tables(result_file, param_filter)
            latex.print_footer(result_file)

        latex.compile_document(filename)

    create_template_table("template-results",
        lambda (fp, dur, ptfs, ppfs): ptfs not in {0.2, 0.3, 0.4})

    create_template_table("template-results-low-prob",
        lambda (fp, dur, ptfs, ppfs): ptfs in {0.2, 0.3, 0.4})


if 'ccpe-comparison-table' in args:
    from data.old_results import OldResults 

    results_to_compare = ('captured', 'fake', 'received ratio', 'tfs', 'pfs')

    old_results = OldResults('results/CCPE/template-results.csv',
        parameters=parameter_names,
        results=results_to_compare)

    template_results = results.Results(template.result_file_path,
        parameters=parameter_names,
        results=results_to_compare)

    result_table = direct_comparison.ResultTable(old_results, template_results)

    def create_comparison_table(name, param_filter=lambda x: True):
        filename = name + ".tex"

        with open(filename, 'w') as result_file:
            latex.print_header(result_file)
            result_table.write_tables(result_file, param_filter)
            latex.print_footer(result_file)

        latex.compile_document(filename)

    create_comparison_table('template-ccpe-comparison')

if 'ccpe-comparison-graph' in args:
    from data.old_results import OldResults 

    results_to_compare = ('captured', 'fake', 'received ratio', 'tfs', 'pfs')

    old_results = OldResults('results/CCPE/template-results.csv',
        parameters=parameter_names,
        results=results_to_compare)

    template_results = results.Results(template.result_file_path,
        parameters=parameter_names,
        results=results_to_compare)

    result_table = direct_comparison.ResultTable(old_results, template_results)

    def create_ccpe_comp_bar(show, pc=False):
        name = 'ccpe-comp-{}-{}'.format(show, "pcdiff" if pc else "diff")

        bar.Grapher(template.graphs_path, result_table, name,
            shows=[show],
            extractor=lambda (diff, pcdiff): pcdiff if pc else diff).create()

        summary.GraphSummary(os.path.join(template.graphs_path, name), 'template-{}'.format(name).replace(" ", "_")).run()

    for result_name in results_to_compare:
        create_ccpe_comp_bar(result_name, pc=True)
        create_ccpe_comp_bar(result_name, pc=False)

    def create_ccpe_comp_bar_pcdiff():
        name = 'ccpe-comp-pcdiff'

        bar.Grapher(template.graphs_path, result_table, name,
            shows=results_to_compare,
            extractor=lambda (diff, pcdiff): pcdiff).create()

        summary.GraphSummary(os.path.join(template.graphs_path, name), 'template-{}'.format(name).replace(" ", "_")).run()

    create_ccpe_comp_bar_pcdiff()
