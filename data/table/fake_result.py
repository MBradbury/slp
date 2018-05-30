# Author: Matthew Bradbury

import itertools

from simulator.Configuration import configuration_rank

from data import latex

# Have one table per network size and configuration
# Specify parameters an results to show

class ResultTable(object):
    def __init__(self, results, fmt=None):
        self.results = results
        self.fmt = fmt

        if fmt is None:
            from data.table.data_formatter import TableDataFormatter
            self.fmt = TableDataFormatter()

    def _column_layout(self):
        parameter_count = len(self.results.parameter_names)
        result_count = len(self.results.result_names)

        inital_header = "|l|"
        parameter_header = "|" + "|".join("l" * parameter_count) + "|"
        result_header = "|" + "|".join("l" * result_count   ) + "|"

        return inital_header + parameter_header + result_header

    def _title_row(self, row):
        titles = [
            latex.escape(self.fmt.format_header(title)[row])
            for title
            in ("source period",) + self.results.parameter_names +  self.results.result_names
        ]

        return "        " + " & ".join(titles) + "\\\\"

    def write_tables(self, stream, param_filter=lambda x: True):
        print('\\vspace{-0.3cm}', file=stream)

        def _custom_sort(name, values):
            if name == "configuration":
                return sorted(values, key=configuration_rank)
            else:
                return sorted(values)

        storted_parameters = [_custom_sort(name, values) for (name, values) in self.results.parameters()]

        for table_key in itertools.product(*storted_parameters):

            try:
                source_periods = sorted(set(self.results.data[table_key].keys()))
            except KeyError as ex:
                print("Unable to find source period for  {}".format(ex))
                continue

            caption = " and ".join([
                "{} \\textbf{{{}}}".format(name, latex.escape(value))
                for (name, value)
                in zip(self.results.global_parameter_names, table_key)
            ])

            print('\\begin{table}[H]', file=stream)
            print('    \\centering', file=stream)
            print('    \\caption{{Results for the {} }} '.format(caption), file=stream)
            print('    \\begin{{tabular}}{{{}}}'.format(self._column_layout()), file=stream)
            print('        \\hline', file=stream)
            print(self._title_row(0), file=stream)
            print(self._title_row(1), file=stream)
            print('        \\hline', file=stream)

            for source_period in source_periods:
                items = self.results.data[table_key][source_period].items()

                items = [(k, v) for (k, v) in items if param_filter(*k)]

                for (params, results) in sorted(items, key=lambda item: item[0]):
                    to_print = [self.fmt.format_value("source period", source_period)]

                    for (name, value) in zip(self.results.parameter_names, params):
                        to_print.append(self.fmt.format_value(name, value))

                    for (name, value) in zip(self.results.result_names, results):
                        to_print.append(self.fmt.format_value(name, value))

                    print(" & ".join(to_print) + "\\\\", file=stream)
                print('        \\hline', file=stream)

            print('    \\end{tabular}', file=stream)
            print('\\end{table}', file=stream)
            print('', file=stream)
