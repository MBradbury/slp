from __future__ import print_function

import numpy

from comparison import ResultTable as BaseResultTable

class ResultTable(BaseResultTable):

    def __init__(self, base_results, comparison_results):

        if base_results.parameter_names != comparison_results.parameter_names:
            raise RuntimeError("Parameter names are not the same")

        super(ResultTable, self).__init__(base_results, comparison_results)

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
                        comp_values = self.comparison_results.data[(size, config)][srcPeriod][base_params]

                        # Provide an empty tuple as the comp params.
                        # This means that results will be grouped in tables by size and config.
                        comp_params = tuple()

                        self.diff \
                            .setdefault((size, config), {}) \
                            .setdefault(comp_params, {}) \
                            .setdefault(srcPeriod, {}) \
                            [base_params] = sub(base_values, comp_values)

                        self.configurations.add(config)
                        self.sizes.add(size)

                    except KeyError as e:
                        print("Skipping {} due to KeyError({})".format((size, config, srcPeriod, base_params), e))
