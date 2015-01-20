from __future__ import print_function

from data.table.comparison import ResultTable as BaseResultTable

class ResultTable(BaseResultTable):

    def __init__(self, base_results, comparison_results):

        if base_results.parameter_names != comparison_results.parameter_names:
            raise RuntimeError("Parameter names are not the same")

        if base_results.result_names != comparison_results.result_names:
            raise RuntimeError("Result names are not the same")

        super(ResultTable, self).__init__(base_results, comparison_results)

        self.parameter_names = base_results.parameter_names
        self.result_names = base_results.result_names

    def _create_diff(self):
        self.diff = {}
        self.data = {}
        self.configurations = set()
        self.sizes = set()

        for ((size, config), items1) in self.base_results.data.items():
            for (src_period, items2) in items1.items():
                for (base_params, base_values) in items2.items():
                    try:
                        comp_values = self.comparison_results.data[(size, config)][src_period][base_params]

                        # Provide an empty tuple as the comp params.
                        # This means that results will be grouped in tables by size and config.
                        comp_params = tuple()

                        self.diff \
                            .setdefault((size, config), {}) \
                            .setdefault(comp_params, {}) \
                            .setdefault(src_period, {}) \
                            [base_params] = self._sub(base_values, comp_values)

                        self.data \
                            .setdefault((size, config), {}) \
                            .setdefault(src_period, {}) \
                            [base_params] = self._sub(base_values, comp_values)

                        self.configurations.add(config)
                        self.sizes.add(size)

                    except KeyError as e:
                        print("Skipping {} due to KeyError({})".format((size, config, src_period, base_params), e))
