#!/usr/bin/env python3
import os
import subprocess
import sys

import algorithm
from data import results, latex
from data.table import fake_result
from data.table.summary_formatter import ShortTableDataFormatter
fmt = ShortTableDataFormatter()


sim_and_algo = {
    "tossim": ["protectionless", "adaptive", "adaptive_spr_notify", "ilprouting"], # template
    "cooja": ["protectionless", "adaptive_spr_notify", "adaptive_spr_notify_lpl", "adaptive_spr_notify_tinyoslpl"],
    "real": ["protectionless", "adaptive_spr_notify", "adaptive_spr_notify_lpl"],
}


titles = {
    "tossim": "TOSSIM",
    "cooja": "Cooja",
    "real": "FlockLab",
    "template": "Static",
    "protectionless": "Protectionless",
    "adaptive": "Dynamic",
    "adaptive_spr_notify": "DynamicSPR",
    "ilprouting": "ILPRouting",
    "adaptive_spr_notify_lpl": "DynamicSPR with Duty Cycling",
    "adaptive_spr_notify_tinyoslpl": "DynamicSPR with TinyOS LPL",
}


parameters = [
    'repeats',
    'captured',
    'time taken',
    'received ratio',
    'norm(sent,time taken)',
    'normal latency',
    'attacker distance',

    # TODO:
    # energy on testbed
]

def results_filter(params):
    return (
        params.get("noise model", "casino-lab") != "casino-lab" or
        params["configuration"] not in ("SourceCorner", "FlockLabSinkCentre") or
        params["source period"] == "0.125" or
        params.get("network size", "") == "5" or
        (params["configuration"] == "FlockLabSinkCentre" and params["source period"] == "0.25")
    )

hide_parameters = [
    'buffer size', 'max walk length', # ILPRouting
    'pr pfs', # Template
]
caption_values = ["network size"]

extractors = {
    # Just get the distance of attacker 0 from node 0 (the source in SourceCorner)
    # On FlockLab it is (1, 0)
    "attacker distance": lambda yvalue: yvalue[(0, 0)] if (0, 0) in yvalue else yvalue[(1, 0)]
}

combined_columns = {
    ('lpl normal early', 'lpl normal late', 'lpl fake early', 'lpl fake late', 'lpl choose early', 'lpl choose late'): ("Duty Cycle", "~ "),
    ('lpl local wakeup', 'lpl remote wakeup', 'lpl delay after receive', 'lpl max cca checks'): ("TinyOS LPL", "~"),

}

filename = "et.tex"

def testbed_results_path(module):
    return os.path.join("results", "real", "flocklab", module.name, module.result_file)

with open(filename, 'w') as result_file:

    print("% !TEX root =  ../Thesis.tex", file=result_file)
    latex.print_header(result_file, orientation="portrait")

    for (sim_name, algos) in sim_and_algo.items():

        print(f"\\section{{{titles[sim_name]}}}", file=result_file)

        for algo in algos:

            print(f"\\subsection{{{titles[algo]}}}", file=result_file)

            algorithm_module = algorithm.import_algorithm(algo, extras=["Analysis"])

            if sim_name != "real":
                result_file_path = algorithm_module.result_file_path(sim_name)
            else:
                result_file_path = testbed_results_path(algorithm_module)

            res = results.Results(
                sim_name, result_file_path,
                parameters=algorithm_module.local_parameter_names,
                results=parameters,
                results_filter=results_filter)

            result_table = fake_result.ResultTable(res, fmt=fmt,
                hide_parameters=hide_parameters, extractors=extractors, caption_values=caption_values, combined_columns=combined_columns,
                longtable=True, caption_prefix=f"Confidence Intervals for {titles[algo]} on {titles[sim_name]} ")

            result_table.write_tables(result_file, font_size="footnotesize\\setlength{\\tabcolsep}{4pt}")

            print()

    latex.print_footer(result_file)

filename_pdf = latex.compile_document(filename)

if True:
    subprocess.call(["xdg-open", filename_pdf])
