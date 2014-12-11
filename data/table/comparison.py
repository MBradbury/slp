from __future__ import print_function

import numpy

from fake_result import ResultTable as BaseResultTable
from data import latex

from simulator.Configuration import configurationRank

class ResultTable(BaseResultTable):
    bad = '\\badcolour'
    good = '\\goodcolour'
    neutral = ''

    @staticmethod
    def _configuration_rank(configuration):
        return configurationRank[configuration] if configuration in configurationRank else len(rank) + 1

    def __init__(self, base_results, comparison_results):

        super(ResultTable, self).__init__(base_results)

        self.base_results = base_results
        self.comparison_results = comparison_results

        self._create_diff()

    def _create_diff(self):
        def sub(b, c):
            # Get the mean of a (mean, stddev) pair if the value is an array.
            # Otherwise just use the value.
            b = [x[0] if isinstance(x, numpy.ndarray) else x for x in b]
            c = [x[0] if isinstance(x, numpy.ndarray) else x for x in c]

            diff = numpy.subtract(c, b)
            pdiff = numpy.array([0 if x == 0 else x / y for (x, y) in zip(diff, numpy.add(c, b) * 0.5)]) * 100.0

            return zip(diff, pdiff)

        self.diff = {}
        self.configurations = set()
        self.sizes = set()

        for ((size, config), items1) in self.base_results.data.items():
            for (srcPeriod, items2) in items1.items():
                for (base_params, base_values) in items2.items():
                    try:
                        for (comp_params, comp_values) in self.comparison_results.data[(size, config)][srcPeriod].items():

                            self.diff \
                                .setdefault((size, config), {}) \
                                .setdefault(comp_params, {}) \
                                .setdefault(srcPeriod, {}) \
                                [base_params] = sub(base_values, comp_values)

                            self.configurations.add(config)
                            self.sizes.add(size)

                    except KeyError as e:
                        print("Skipping {} due to KeyError({})".format((size, config, srcPeriod), e))

    def write_tables(self, stream, param_filter = lambda x: True):
        title_order = self.base_results.parameter_names + self.base_results.result_names
                    
        print('\\vspace{-0.3cm}', file=stream)

        for configuration in sorted(self.configurations, key=lambda x: configurationRank[x]):
            for size in sorted(self.sizes):
                table_key = (size, configuration)

                for comp_param in sorted(set(self.diff[table_key].keys())):

                    print('\\begin{table}[H]', file=stream)
                    print('    \\centering', file=stream)
                    print('    \\begin{{tabular}}{{{}}}'.format(self._column_layout()), file=stream)
                    print('        \\hline', file=stream)
                    print(self._title_row(0), file=stream)
                    print(self._title_row(1), file=stream)
                    print('        \\hline', file=stream)

                    for source_period in sorted(set(self.diff[table_key][comp_param].keys())):

                        items = self.diff[table_key][comp_param][source_period].items()

                        items = filter(lambda (k, v): param_filter(k), items)

                        for (params, results) in sorted(items, key=lambda (x, y): x):                    
                            to_print = [self._var_fmt("source period", source_period)]

                            for name, value in zip(self.results.parameter_names, params):
                                to_print.append(self._var_fmt(name, value))

                            for name, value in zip(self.results.result_names, results):
                                to_print.append(self._var_fmt(name, value))

                            print(" & ".join(to_print) + "\\\\", file=stream)
                        print('        \\hline', file=stream)

                    print('    \\end{tabular}', file=stream)

                    if len(comp_param) == 0 and len(self.comparison_results.parameter_names) == 0:
                        print('\\caption{{Comparison results for the size {} and configuration {}}}'.format(size, configuration), file=stream)
                    else:
                        print('\\caption{{Comparison results for the size {}, configuration {} and compared parameters {}}}'.format(
                            size, configuration, latex.escape(str(zip(self.comparison_results.parameter_names, comp_param)))), file=stream)

                    print('\\end{table}', file=stream)
                    print('', file=stream)

    def _var_fmt(self, name, value):
        def colour_neg(value):
            if value < 0:
                return ResultTable.good
            else:
                return ResultTable.bad

        def colour_pos(value):
            if value > 0:
                return ResultTable.good
            else:
                return ResultTable.bad

        if name == "tfs" or name == "pfs":
            return "${:+.1f}$".format(*value)
        elif name == "received ratio":
            return "${} {:+.1f}$".format(colour_pos(value[0]), *value)
        elif name == "fake":
            return "${} {:+.0f}$ $({:+.0f}\\%)$".format(colour_neg(value[0]), *value)
        elif name == "ssd":
            return "${} {:+.2f}$".format(colour_neg(value[0]), *value)
        elif name == "normal latency":
            return "${} {:+.2f}$".format(colour_neg(value[0]), value[0] * 1000, value[1])
        elif name == "captured":
            return "${} {:+.2f}$ $({:+.0f}\\%)$".format(colour_neg(value[0]), *value)
        elif name == "time taken" or name == "safety period":
            return "${} {:+.2f}$ $({:+.0f}\\%)$".format(colour_neg(value[0]), *value)
        else:
            return super(ResultTable, self)._var_fmt(name, value)
