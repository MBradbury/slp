from __future__ import print_function

import os

import data.util
from data import latex
from data.graph.versus import Grapher as GrapherBase

class Grapher(GrapherBase):
    def __init__(self, output_directory,
                 result_name, xaxis, yaxis, vary, yextractor=lambda x: x):

        super(Grapher, self).__init__(
            output_directory, result_name, xaxis, yaxis, vary, yextractor
        )

        self.max_label = 'Maximum'
        self.min_label = 'Minimum'
        self.comparison_label = 'Comparison'
        self.baseline_label = 'Baseline'

        self.vvalue_label_converter = str

    def create(self, comparison_results, actual_results, baseline_results=None):
        print('Removing existing directories')
        data.util.remove_dirtree(os.path.join(self.output_directory, self.result_name))

        print('Creating {} graph files'.format(self.result_name))

        dat = {}

        min_comparison_results = {}
        max_comparison_results = {}
        baseline_comparison_results = {}

        # Find the min and max results over all parameter combinations 
        for (data_key, items1) in comparison_results.data.items():
            for (src_period, items2) in items1.items():

                local_min = None
                local_max = None

                for (params, results) in items2.items():
                    yvalue_index = comparison_results.result_names.index(self.yaxis)
                    yvalue = results[yvalue_index]
                    yvalue = self.yextractor(yvalue)

                    local_min = yvalue if local_min is None else min(local_min, yvalue)
                    local_max = yvalue if local_max is None else max(local_max, yvalue)

                min_comparison_results.setdefault(data_key, {})[src_period] = local_min
                max_comparison_results.setdefault(data_key, {})[src_period] = local_max

        if baseline_results is not None:
            for (data_key, items1) in baseline_results.data.items():
                for (src_period, items2) in items1.items():
                    results = items2[tuple()]

                    yvalue_index = baseline_results.result_names.index(self.yaxis)
                    yvalue = results[yvalue_index]
                    yvalue = self.yextractor(yvalue)

                    baseline_comparison_results.setdefault(data_key, {})[src_period] = yvalue

        # Extract the data we want to display
        for (data_key, items1) in actual_results.data.items():
            for (src_period, items2) in items1.items():
                for (params, results) in items2.items():

                    key_names = self._key_names_base + actual_results.parameter_names

                    values = list(data_key)
                    values.append(src_period)
                    values.extend(params)

                    (key_names, values, xvalue) = self._remove_index(key_names, values, self.xaxis)
                    (key_names, values, vvalue) = self._remove_index(key_names, values, self.vary)

                    #if self.xaxis == 'network size':
                    #    xvalue = xvalue ** 2

                    key_names = tuple(key_names)
                    values = tuple(values)

                    yvalue_index = actual_results.result_names.index(self.yaxis)
                    yvalue = results[yvalue_index]
                    yvalue = self.yextractor(yvalue)

                    comp_label = "{} ({})".format(self.comparison_label, self.vvalue_label_converter(vvalue))

                    if data_key in max_comparison_results:
                        dat.setdefault((key_names, values), {})[(xvalue, self.max_label)] = max_comparison_results[data_key].get(src_period)

                        dat.setdefault((key_names, values), {})[(xvalue, comp_label)] = yvalue

                        dat.setdefault((key_names, values), {})[(xvalue, self.min_label)] = min_comparison_results[data_key].get(src_period)

                        if baseline_results is not None:
                            dat.setdefault((key_names, values), {})[(xvalue, self.baseline_label)] = baseline_comparison_results[data_key].get(src_period)


        for ((key_names, key_values), values) in dat.items():
            self._create_plot(key_names, key_values, values)

        self._create_graphs(self.result_name)

    def _order_keys(self, keys):
        """Order the keys alphabetically, except for the baseline label.
        This is because it looks better if baseline is included last.
        Some graphs will not include a baseline, so having baseline last
        makes the key colours and point type the same, irrespective of
        whether baseline is graphed or not."""
        sorted_keys = list(sorted(keys))
        if self.baseline_label in keys:
            sorted_keys.remove(self.baseline_label)
            sorted_keys.append(self.baseline_label)
        return sorted_keys
