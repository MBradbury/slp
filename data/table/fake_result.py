# Author: Matthew Bradbury
from __future__ import print_function

import csv, math, sys, ast

import numpy

from simulator.Configuration import configurationRank

from data.latex import latex

# Have one table per network size and configuration
# Specify parameters an results to show

class ResultTable:
    def __init__(self, results, param_filter = lambda x: True):
        self.results = results
        self.param_filter = param_filter

    def _column_layout(self):
        parameter_count = len(self.results.parameter_names)
        result_count = len(self.results.result_names)

        a = "|l|"
        b = "|" + "|".join("l" * parameter_count) + "|"
        c = "|" + "|".join("l" * result_count   ) + "|"

        return a + b + c

    def _convert_title_row(self, name, row):
        try:
            return {
                "source period": ("$P_{src}$", "(sec)"),
                "fake period": ("$P_{fs}$", "(sec)"),
                "temp fake duration": ("Dur", "(sec)"),
                "pr(tfs)": ("P[TFS]", "(\%)"),
                "pr(pfs)": ("P[PFS]", "(\%)"),
                "captured": ("Cap", "(\%)"),
                "fake": ("Fake", "Messages"),
                "received ratio": ("Received", "(\%)"),
                "tfs": ("TFS", "~"),
                "pfs": ("PFS", "~"),
                "pull back hops": ("Pull Back", "Messages"),
                "ssd": ("$\\Delta_{ss}$", "(hops)"),
                "normal latency": ("Latency", "(msec)"),
                "technique": ("Technique", "~"),
            }[name][row]
        except KeyError as e:
            print("Failed to find the name {} for row {} : {}".format(name, row, e), file=sys.stderr)
            return name

    def _title_row(self, row):
        a = map(lambda x: self._convert_title_row(x, row), ["source period"] + self.results.parameter_names +  self.results.result_names)
        return "        " + " & ".join(a) + "\\\\"

    def _var_fmt(self, name, value):
        if name == "source period" or name == "fake period":
            return "{}".format(value)
        elif name == "duration":
            return "{}".format(value)
        elif name == "pr(tfs)" or name == "pr(pfs)":
            return "{:.0f}".format(value * 100.0)
        elif name == "tfs" or name == "pfs":
            return "{:.1f}".format(value[0])
        elif name == "technique":
            return latex.escape(value)
        elif isinstance(value, float):
            return "{:.2f}".format(value)
        elif name == "received ratio":
            return "{:.1f} $\pm$ {:.1f}".format(*value)
        elif name == "fake":
            return "{:.0f} $\pm$ {:.0f}".format(*value)
        elif name == "ssd":
            return "{:.1f} $\pm$ {:.1f}".format(*value)
        elif name == "normal latency":
            return "{:.0f} $\pm$ {:.0f}".format(*(value * 1000))
        else:
            return "{:.3f} $\pm$ {:.3f}".format(*value)


    def write_tables(self, stream):
        title_order = self.results.parameter_names + self.results.result_names
                    
        print('\\vspace{-0.3cm}', file=stream)

        for configuration in sorted(self.results.configurations, key=lambda x: configurationRank[x]):
            for size in sorted(self.results.sizes):
                print('\\begin{table}[H]', file=stream)
                print('    \\centering', file=stream)
                print('    \\begin{{tabular}}{{{}}}'.format(self._column_layout()), file=stream)
                print('        \\hline', file=stream)
                print(self._title_row(0), file=stream)
                print(self._title_row(1), file=stream)
                print('        \\hline', file=stream)

                table_key = (size, configuration)

                source_periods = sorted(set(self.results.data[table_key].keys()))

                for source_period in source_periods:
                    items = self.results.data[table_key][source_period].items()

                    items = filter(lambda (k, v): self.param_filter(k), items)

                    for (params, results) in sorted(items, key=lambda (x, y): x):                    
                        to_print = [self._var_fmt("source period", source_period)]

                        for name, value in zip(self.results.parameter_names, params):
                            to_print.append(self._var_fmt(name, value))

                        for name, value in zip(self.results.result_names, results):
                            to_print.append(self._var_fmt(name, value))

                        print(" & ".join(to_print) + "\\\\", file=stream)
                    print('        \\hline', file=stream)
                    

                print('    \\end{tabular}', file=stream)
                print('\\caption{{Template results for the size {} and configuration {}}}'.format(size, configuration), file=stream)
                print('\\end{table}', file=stream)
                print('', file=stream)
