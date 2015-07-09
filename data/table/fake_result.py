# Author: Matthew Bradbury
from __future__ import print_function

import sys, itertools

from simulator.Configuration import configuration_rank

from data import latex

# Have one table per network size and configuration
# Specify parameters an results to show

class ResultTable(object):
    def __init__(self, results):
        self.results = results

    def _column_layout(self):
        parameter_count = len(self.results.parameter_names)
        result_count = len(self.results.result_names)

        inital_header = "|l|"
        parameter_header = "|" + "|".join("l" * parameter_count) + "|"
        result_header = "|" + "|".join("l" * result_count   ) + "|"

        return inital_header + parameter_header + result_header

    def _convert_title_row(self, name, row):

        if self.results.is_normalised_name(name):
            (norm_name, div_name) = self.results.get_normalised_names(name)

            norm_value = self._convert_title_row(norm_name, row)
            div_value = self._convert_title_row(div_name, row)

            return "{} / {}".format(norm_value, div_value)

        try:
            return {
                "network size": ("Network Size", "nodes"),

                "source period": ("$P_{src}$", "(sec)"),
                "fake period": ("$P_{fs}$", "(sec)"),
                "temp fake duration": ("Dur", "(sec)"),
                "pr(tfs)": ("P[TFS]", "(\\%)"),
                "pr(pfs)": ("P[PFS]", "(\\%)"),
                "captured": ("Cap", "(\\%)"),
                "fake": ("Fake", "Messages"),
                "received ratio": ("Received", "(\\%)"),
                "tfs": ("TFS", "~"),
                "pfs": ("PFS", "~"),
                "pull back hops": ("Pull Back", "Messages"),
                "ssd": ("$\\Delta_{ss}$", "(hops)"),
                "normal latency": ("Laten", "(msec)"),
                "approach": ("Approach", "~"),
                "time taken": ("Time", "(sec)"),
                "safety period": ("Safety Period", "(sec)"),
                "wall time": ("Wall Time", "(sec)"),
                "event count": ("Event Count", ""),
                
                "walk length": ("Walk Length", "(hops)"),
                "walk retries": ("Walk", "Retries"),
                "paths reached end": ("Paths Ended", "(\\%)"),
            }[name][row]
        except KeyError as ex:
            print("Failed to find the name '{}' for row {}. Using default. : {}".format(name, row, ex), file=sys.stderr)
            return name

    def _title_row(self, row):
        titles = [
            self._convert_title_row(title, row)
            for title
            in ["source period"] + self.results.parameter_names +  self.results.result_names
        ]

        return "        " + " & ".join(titles) + "\\\\"

    def _var_fmt(self, name, value):
        if value is None:
            return "None"
        elif name in {"source period", "fake period", "walk length", "walk retries"}:
            return "${}$".format(value)
        elif name == "duration" or name == "temp fake duration":
            return "${:.0f}$".format(value)
        elif name == "pr(tfs)" or name == "pr(pfs)":
            return "${:.0f}$".format(value * 100.0)
        elif name == "tfs" or name == "pfs":
            return "${:.1f}$".format(value[0])
        elif name in {"approach", "landmark node"}:
            return latex.escape(value)
        elif isinstance(value, float):
            return "${:.2f}$".format(value)
        elif name in {"received ratio", "ssd"}:
            return "${:.1f} \\pm {:.1f}$".format(value[0], value[1])
        elif name == "fake":
            return "${:.0f} \\pm {:.0f}$".format(value[0], value[1])
        elif name == "normal latency":
            return "${:.0f} \\pm {:.0f}$".format(value[0], value[1])
        elif name == "paths reached end":
            return "${:.1f} \\pm {:.1f}$".format(value[0], value[1])
        else:
            return "${:.3f} \\pm {:.3f}$".format(value[0], value[1])


    def write_tables(self, stream, param_filter=lambda x: True):
        print('\\vspace{-0.3cm}', file=stream)

        sizes = sorted(self.results.sizes)
        configurations = sorted(self.results.configurations, key=configuration_rank)
        attacker_models = sorted(self.results.attacker_models)
        noise_models = sorted(self.results.noise_models)
        communication_models = sorted(self.results.communication_models)

        for table_key in itertools.product(sizes, configurations, attacker_models, noise_models, communication_models):

            (size, configuration, attacker_model, noise_model, communication_model) = table_key

            try:
                source_periods = sorted(set(self.results.data[table_key].keys()))
            except KeyError:
                continue

            print('\\begin{table}[H]', file=stream)
            print('    \\centering', file=stream)
            print('    \\begin{{tabular}}{{{}}}'.format(self._column_layout()), file=stream)
            print('        \\hline', file=stream)
            print(self._title_row(0), file=stream)
            print(self._title_row(1), file=stream)
            print('        \\hline', file=stream)

            for source_period in source_periods:
                items = self.results.data[table_key][source_period].items()

                items = [(k, v) for (k, v) in items if param_filter(k)]

                for (params, results) in sorted(items, key=lambda (x, y): x):
                    to_print = [self._var_fmt("source period", source_period)]

                    for (name, value) in zip(self.results.parameter_names, params):
                        to_print.append(self._var_fmt(name, value))

                    for (name, value) in zip(self.results.result_names, results):
                        to_print.append(self._var_fmt(name, value))

                    print(" & ".join(to_print) + "\\\\", file=stream)
                print('        \\hline', file=stream)

            print('    \\end{tabular}', file=stream)
            print('\\caption{{Results for the size \\textbf{{{}}} and configuration \\textbf{{{}}} and attacker model \\textbf{{{}}} and noise model \\textbf{{{}}} and communication model \\textbf{{{}}} }} '.format(
                size, configuration, attacker_model, noise_model, communication_model), file=stream)
            print('\\end{table}', file=stream)
            print('', file=stream)
