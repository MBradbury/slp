# Author: Matthew Bradbury

import itertools

from simulator.Configuration import configuration_rank

from data import latex

# Have one table per network size and configuration
# Specify parameters an results to show

class ResultTable(object):
    def __init__(self, results, fmt=None, hide_parameters=None, extractors=None, resize_to_width=False, longtable=True, caption_values=None, caption_prefix="", combined_columns=None):
        self.results = results
        self.fmt = fmt
        self.parameter_names_to_use = tuple([x for x in self.results.parameter_names if x not in hide_parameters]) if hide_parameters else self.results.parameter_names
        self.extractors = extractors
        self.resize_to_width = resize_to_width
        self.caption_values = caption_values
        self.longtable = longtable
        self.caption_prefix = caption_prefix

        self.combined_columns = {}

        if combined_columns:
            for params, header in combined_columns.items():
                if all(param in self.results.parameter_names for param in params):
                    self.parameter_names_to_use = tuple([x for x in self.parameter_names_to_use if x not in params])

                    self.combined_columns[params] = header

        if fmt is None:
            from data.table.data_formatter import TableDataFormatter
            self.fmt = TableDataFormatter()

    def _column_layout(self):
        parameter_count = len(self.parameter_names_to_use) + len(self.combined_columns)
        result_count = len(self.results.result_names)

        inital_header = "|l|" # Source Period
        parameter_header = "|".join("c" * parameter_count) + "|" if parameter_count else ""
        result_header = "|" + "|".join("c" * result_count) + "|"

        return inital_header + parameter_header + result_header

    def _title_row(self, row):
        titles = [
            "{" + self.fmt.format_header(title)[row] + "}"
            for title
            in ("source period",) + self.parameter_names_to_use
        ]

        for (combined, header) in self.combined_columns.items():
            titles.append(header[row])

        titles.extend([
            "{" + self.fmt.format_header(title)[row] + "}"
            for title
            in self.results.result_names
        ])

        return "        " + "\\rowcolor{gray!40}" + " & ".join(titles) + "\\\\"

    def _extract(self, name, value):
        return self.extractors.get(name, lambda x: x)(value)

    def caption_formatter(self, table_key):
        caption = " and ".join([
                "{} {}".format(name.title(), latex.escape(value))
                for (name, value)
                in zip(self.results.global_parameter_names, table_key)
                if self.caption_values is None or name in self.caption_values
            ])

        return self.caption_prefix + caption

    def write_tables(self, stream, param_filter=lambda *args: True, font_size=None):
        def _custom_sort(name, values):
            if name == "configuration":
                return sorted(values, key=configuration_rank)
            elif name == "network size":
                return map(str, sorted(map(int, values)))
            else:
                return sorted(values)

        storted_parameters = [_custom_sort(name, values) for (name, values) in self.results.parameters()]

        for table_key in itertools.product(*storted_parameters):

            try:
                source_periods = sorted(set(self.results.data[table_key].keys()))
            except KeyError as ex:
                print("Unable to find source period for  {}".format(ex))
                continue

            caption = self.caption_formatter(table_key)

            if not self.longtable:
                print('\\begin{table}[H]', file=stream)
                print('    \\centering', file=stream)
                
            else:
                print('\\begin{center}', file=stream)

            if font_size:
                print('    \\{}'.format(font_size), file=stream)
            print('    \\rowcolors{2}{white}{gray!15}', file=stream)

            if self.longtable:
                if self.resize_to_width:
                    print('\\begin{{longtabu}} to \\textwidth {{{}}}'.format(self._column_layout()), file=stream)
                else:
                    print('\\begin{{longtabu}} {{{}}}'.format(self._column_layout()), file=stream)

                print('\\caption{{\\normalsize {}}}\\\\'.format(caption), file=stream)

            else:
                if self.resize_to_width:
                    print('    \\resizebox{\\textwidth}{!}{%', file=stream)
                print('    \\begin{{tabular}}{{{}}}'.format(self._column_layout()), file=stream)

            print('        \\hline', file=stream)
            print(self._title_row(0), file=stream)
            print(self._title_row(1), file=stream)
            print('        \\hline', file=stream)

            #if self.longtable:
            #    print('        \\endhead', file=stream)

            for source_period in source_periods:
                items = self.results.data[table_key][source_period].items()

                items = [(k, v) for (k, v) in items if param_filter(*k)]

                for (params, results) in sorted(items, key=lambda item: item[0]):
                    to_print = [self.fmt.format_value("source period", source_period)]

                    paramsd = dict(zip(self.results.parameter_names, params))

                    for (name, value) in paramsd.items():
                        if name in self.parameter_names_to_use:
                            to_print.append(self.fmt.format_value(name, value))

                    for (combined, header) in self.combined_columns.items():
                        loc = []
                        for comb in combined:
                            loc.append(self.fmt.format_value(comb, paramsd[comb]))

                        to_print.append("(" + ", ".join(loc) + ")")


                    for (name, value) in zip(self.results.result_names, results):
                        to_print.append(self.fmt.format_value(name, self._extract(name, value)))

                    print(" & ".join(to_print) + "\\\\", file=stream)
                print('        \\hline', file=stream)

            if not self.longtable:
                print('    \\end{tabular}', file=stream)

                if self.resize_to_width:
                    print('    }%', file=stream)
                
                print('\\caption{{{}}} '.format(caption), file=stream)

                print('\\end{table}', file=stream)

            else:
                print('\\end{longtabu}', file=stream)
                print('\\end{center}', file=stream)

            print('\\vspace{-0.5cm}', file=stream)

            print('', file=stream)
