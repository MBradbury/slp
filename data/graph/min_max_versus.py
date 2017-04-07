from __future__ import print_function

import os

import data.util
from data.graph.versus import Grapher as GrapherBase

class Grapher(GrapherBase):
    def __init__(self, output_directory,
                 result_name, xaxis, yaxis, vary, yextractor=None):

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

        min_comparison_results = []
        max_comparison_results = []
        baseline_comparison_results = {}

        # Handle the case where a single comparison result is provided
        if not isinstance(comparison_results, list):
            comparison_results = [comparison_results]

            self.max_label = [self.max_label]
            self.min_label = [self.min_label]

        for comparison_result in comparison_results:

            min_comparison_result = {}
            max_comparison_result = {}

            # Find the min and max results over all parameter combinations 
            for (data_key, items1) in comparison_result.data.items():
                for (src_period, items2) in items1.items():

                    local_min = None
                    local_max = None

                    for (params, results) in items2.items():
                        yvalue_index = comparison_result.result_names.index(self.yaxis)
                        yvalue = results[yvalue_index]
                        yvalue = self._value_extractor(yvalue)

                        local_min = yvalue if local_min is None else min(local_min, yvalue)
                        local_max = yvalue if local_max is None else max(local_max, yvalue)

                    min_comparison_result.setdefault(data_key, {})[src_period] = local_min
                    max_comparison_result.setdefault(data_key, {})[src_period] = local_max

            min_comparison_results.append(min_comparison_result)
            max_comparison_results.append(max_comparison_result)

        if baseline_results is not None:
            for (data_key, items1) in baseline_results.data.items():
                for (src_period, items2) in items1.items():
                    results = items2[tuple()]

                    yvalue_index = baseline_results.result_names.index(self.yaxis)
                    yvalue = results[yvalue_index]
                    yvalue = self._value_extractor(yvalue)

                    baseline_comparison_results.setdefault(data_key, {})[src_period] = yvalue

        # Extract the data we want to display
        for (data_key, items1) in actual_results.data.items():
            for (src_period, items2) in items1.items():
                for (params, results) in items2.items():

                    key_names = self._key_names_base + actual_results.parameter_names

                    values = list(data_key)
                    values.append(src_period)
                    values.extend(params)

                    (key_names, values, xvalue) = self.remove_index(key_names, values, self.xaxis)
                    (key_names, values, vvalue) = self.remove_index(key_names, values, self.vary)

                    #if self.xaxis == 'network size':
                    #    xvalue = xvalue ** 2

                    key_names = tuple(key_names)
                    values = tuple(values)

                    yvalue_index = actual_results.result_names.index(self.yaxis)
                    yvalue = results[yvalue_index]
                    yvalue = self._value_extractor(yvalue)

                    comp_label = "{} ({})".format(self.comparison_label, self.vvalue_label_converter(vvalue))

                    dat.setdefault((key_names, values), {})[(xvalue, comp_label)] = yvalue

                    for (i, (max_comparison_result, min_comparison_result)) in enumerate(zip(max_comparison_results, min_comparison_results)):

                        if data_key in max_comparison_result and data_key in min_comparison_result:

                            dat.setdefault((key_names, values), {})[(xvalue, self.max_label[i])] = max_comparison_result[data_key].get(src_period)

                            dat.setdefault((key_names, values), {})[(xvalue, self.min_label[i])] = min_comparison_result[data_key].get(src_period)

                        else:
                            print("Not processing {} as it is not in the min/max data:".format(data_key))
                            for key in sorted(max_comparison_result):
                                print("\t{}".format(key))

                    if baseline_results is not None:
                        dat.setdefault((key_names, values), {})[(xvalue, self.baseline_label)] = baseline_comparison_results[data_key].get(src_period)

        return self._build_plots_from_dat(dat)

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
