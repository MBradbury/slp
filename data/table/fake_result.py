# Author: Matthew Bradbury
from __future__ import print_function

import csv, math, sys, ast

import numpy

from simulator.Configuration import configurationRank

from data.latex import latex

# Have one table per network size and configuration
# Specify parameters an results to show

class ResultTable:
    
    @staticmethod
    def extractAverageAndSddev(value):
        split = value.split('(')

        mean = float(split[0])
        var = float(split[1].strip(')'))

        return numpy.array((mean, math.sqrt(var)))

    def __init__(self, result_file, parameters, results):
        self.result_file = result_file
        self.parameter_names = list(parameters)
        self.result_names = list(results)

    def _process(self, name, headers, values):
        index = headers.index(name)
        value = values[index]

        if name == 'captured':
            return float(value) * 100.0
        elif name == 'received ratio':
            return self.extractAverageAndSddev(value) * 100.0
        elif '(' in value:
            return self.extractAverageAndSddev(value)
        elif name == 'technique':
            return value
        else:
            return ast.literal_eval(value)

    def _read_results(self):

        self.table_keys = set()
        self.results = {}

        self.sizes = set()
        self.configurations = set()

        with open(self.result_file, 'r') as f:

            seenFirst = False
            
            reader = csv.reader(f, delimiter='|')
            
            headers = []
            
            for values in reader:
                # Check if we have seen the first line
                # We do this because we want to ignore it
                if seenFirst:

                    size = int(values[ headers.index('network size') ])
                    srcPeriod = float(values[ headers.index('source period') ])
                    config = values[ headers.index('configuration') ]

                    table_key = (size, config)

                    self.sizes.add(size)
                    self.configurations.add(config)

                    params = tuple([self._process(name, headers, values) for name in self.parameter_names])
                    results = tuple([self._process(name, headers, values) for name in self.result_names])
                
                    self.results.setdefault(table_key, {}).setdefault(srcPeriod, {})[params] = results

                else:
                    seenFirst = True
                    headers = values

    def _column_layout(self):
        parameter_count = len(self.parameter_names)
        result_count = len(self.result_names)

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
                "pr(tfs)": ("Pr(TFS)", "(\%)"),
                "pr(pfs)": ("Pr(PFS)", "(\%)"),
                "captured": ("Cap", "(\%)"),
                "fake": ("Fake", "Messages"),
                "received ratio": ("Received", "(\%)"),
                "tfs": ("TFS", "~"),
                "pfs": ("PFS", "~"),
                "pull back hops": ("Pull Back", "Messages"),
                "ssd": ("$\\Delta_{ss}$", "(hops)"),
                "normal latency": ("Latency", "(sec)"),
                "technique": ("Technique", "~"),
            }[name][row]
        except KeyError as e:
            print("Failed to find the name {} for row {} : {}".format(name, row, e), file=sys.stderr)
            return name

    def _title_row(self, row):
        a = map(lambda x: self._convert_title_row(x, row), ["source period"] + self.parameter_names +  self.result_names)
        return "        " + " & ".join(a) + "\\\\"

    def _var_fmt(self, name, value):
        if name == "source period" or name == "fake period":
            return "{}".format(value)
        elif name == "duration":
            return "{}".format(value)
        elif name == "pr(tfs)" or name == "pr(pfs)":
            return "{:.0f}".format(value * 100.0)
        elif name == "tfs" or name == "pfs":
            return "{:.0f}".format(value[0])
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
        else:
            return "{:.3f} $\pm$ {:.3f}".format(*value)


    def write_tables(self, stream):
        self._read_results()

        title_order = self.parameter_names + self.result_names
                    
        print('\\vspace{-0.3cm}', file=stream)

        for configuration in sorted(self.configurations, key=lambda x: configurationRank[x]):
            for size in sorted(self.sizes):
                print('\\begin{table}[H]', file=stream)
                print('    \\centering', file=stream)
                print('    \\begin{{tabular}}{{{}}}'.format(self._column_layout()), file=stream)
                print('        \\hline', file=stream)
                print(self._title_row(0), file=stream)
                print(self._title_row(1), file=stream)
                print('        \\hline', file=stream)

                table_key = (size, configuration)

                source_periods = sorted(set(self.results[table_key].keys()))

                for source_period in source_periods:
                    items = self.results[table_key][source_period].items()

                    for (params, results) in sorted(items, key=lambda (x, y): x):                    
                        to_print = [self._var_fmt("source period", source_period)]

                        for name, value in zip(self.parameter_names, params):
                            to_print.append(self._var_fmt(name, value))

                        for name, value in zip(self.result_names, results):
                            to_print.append(self._var_fmt(name, value))

                        print(" & ".join(to_print) + "\\\\", file=stream)
                    print('        \\hline', file=stream)
                    

                print('    \\end{tabular}', file=stream)
                print('\\caption{{Template results for the size {} and configuration {}}}'.format(size, configuration), file=stream)
                print('\\end{table}', file=stream)
                print('', file=stream)
