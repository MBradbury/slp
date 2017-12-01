from __future__ import print_function

import numpy

from data.table.fake_result import ResultTable as BaseResultTable
from data import latex

from simulator.Configuration import configuration_rank

class ResultTable(BaseResultTable):
    bad = '\\badcolour'
    good = '\\goodcolour'
    neutral = ''

    def __init__(self, base_results, comparison_results, fmt=None):

        super(ResultTable, self).__init__(base_results, fmt=fmt)

        self.base_results = base_results
        self.comparison_results = comparison_results

        self.diff = {}
        self.configurations = set()
        self.sizes = set()

        self._create_diff()

    def _sub(self, base_values, comp_values):
        def relative_change(old_value, new_value):
            old_value = float(old_value)
            new_value = float(new_value)

            change = new_value - old_value
            try:
                divisor = abs(old_value)
                return (change / divisor) * 100.0
            except ZeroDivisionError:
                return None

        # Get the mean of a (mean, stddev) pair if the value is an array.
        # Otherwise just use the value.
        base_values = [x[0] if isinstance(x, numpy.ndarray) else x for x in base_values]
        comp_values = [x[0] if isinstance(x, numpy.ndarray) else x for x in comp_values]

        diff = numpy.subtract(comp_values, base_values)
        reldiff = numpy.array([relative_change(x, y) for (x, y) in zip(base_values, comp_values)])

        return zip(diff, reldiff)

    def _create_diff(self):
        for ((size, config), items1) in self.base_results.data.items():
            for (src_period, items2) in items1.items():
                for (base_params, base_values) in items2.items():
                    try:
                        items3 = self.comparison_results.data[(size, config)][src_period].items()
                        for (comp_params, comp_values) in items3:

                            self.diff \
                                .setdefault((size, config), {}) \
                                .setdefault(comp_params, {}) \
                                .setdefault(src_period, {}) \
                                [base_params] = self._sub(base_values, comp_values)

                            self.configurations.add(config)
                            self.sizes.add(size)

                    except KeyError as ex:
                        print("Skipping {} due to KeyError({})".format(
                            (size, config, src_period), ex
                        ))

    def write_tables(self, stream, param_filter=lambda *args: True):
        print('\\vspace{-0.3cm}', file=stream)

        for configuration in sorted(self.configurations, key=configuration_rank):
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

                        items = [(k, v) for (k, v) in items if param_filter(*k)]

                        for (params, results) in sorted(items, key=lambda item: item[0]):
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

        def with_rel_diff(fn, value, fmt):
            if value[1] is not None:
                return ("${} " + fmt + "$ $({:+.0f}\\%)$").format(fn(value[0]), value[0], value[1])
            else:
                return ("${} " + fmt + "$ $(\\mathrm{{N/A}}\\%)$").format(fn(value[0]), value[0])

        if name == "tfs" or name == "pfs":
            return "${:+.1f}$".format(value[0])
        elif name == "received ratio":
            return "${} {:+.1f}$".format(colour_pos(value[0]), value[0])
        elif name == "fake":
            return with_rel_diff(colour_neg, value, "{:+.0f}")
        elif name == "ssd":
            return "${} {:+.2f}$".format(colour_neg(value[0]), value[0])
        elif name == "normal latency":
            return "${} {:+.2f}$".format(colour_neg(value[0]), value[0] * 1000)
        elif name == "captured":
            return with_rel_diff(colour_neg, value, "{:+.2f}")
        elif name == "time taken" or name == "safety period":
            return with_rel_diff(colour_neg, value, "{:+.2f}")
        else:
            return super(ResultTable, self)._var_fmt(name, value)
