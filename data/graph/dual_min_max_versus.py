from __future__ import print_function

import os

import data.util
from data.graph.dual_versus import Grapher as GrapherBase

class Grapher(GrapherBase):
    def __init__(self, sim_name, output_directory,
                 result_name, xaxis, yaxis1, yaxis2, vary, yextractor=lambda x: x):

        super(Grapher, self).__init__(
            sim_name, output_directory, result_name, xaxis, yaxis1, yaxis2, vary, yextractor
        )

        self.max_label = 'Maximum'
        self.min_label = 'Minimum'
        self.comparison_label = 'Comparison'
        self.baseline_label = 'Baseline'

        self.vvalue_label_converter = str

    def create(self, comparison_results, actual_results, baseline_results=None):
        print('Removing existing directories')
        data.util.remove_dirtree(os.path.join(self.output_directory, self.result_name))

        print(f'Creating {self.result_name} graph files')

        dat1 = {}
        dat2 = {}

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

                    local_min_yvalue2 = None
                    local_max_yvalue2 = None

                    for (params, results) in items2.items():
                        yvalue1_index = comparison_result.result_names.index(self.yaxis1)
                        yvalue1 = results[yvalue1_index]
                        yvalue1 = self.yextractor(yvalue1)

                        # yvalue2 is the other bit of data we want to graph on the other axis.
                        # We do not want to find the min or max of this, but want to find the
                        # yvalue2 that corresponds to the min/max of yvalue1
                        yvalue2_index = comparison_result.result_names.index(self.yaxis2)
                        yvalue2 = results[yvalue2_index]
                        yvalue2 = self.yextractor(yvalue2)

                        if local_min is None or yvalue1 < local_min:
                            local_min = yvalue1
                            local_min_yvalue2 = yvalue2

                        if local_max is None or yvalue1 > local_max:
                            local_max = yvalue1
                            local_max_yvalue2 = yvalue2

                    min_comparison_result.setdefault(data_key, {})[src_period] = (local_min, local_min_yvalue2)
                    max_comparison_result.setdefault(data_key, {})[src_period] = (local_max, local_max_yvalue2)

            min_comparison_results.append(min_comparison_result)
            max_comparison_results.append(max_comparison_result)

        if baseline_results is not None:
            for (data_key, items1) in baseline_results.data.items():
                for (src_period, items2) in items1.items():
                    results = items2[tuple()]

                    yvalue_index = baseline_results.result_names.index(self.yaxis1)
                    yvalue = results[yvalue_index]
                    yvalue = self.yextractor(yvalue)

                    yvalue2_index = baseline_results.result_names.index(self.yaxis2)
                    yvalue2 = results[yvalue2_index]
                    yvalue2 = self.yextractor(yvalue2)

                    baseline_comparison_results.setdefault(data_key, {})[src_period] = (yvalue, yvalue2)

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

                    yvalue_index = actual_results.result_names.index(self.yaxis1)
                    yvalue = results[yvalue_index]
                    yvalue = self.yextractor(yvalue)

                    value2_index = actual_results.result_names.index(self.yaxis2)
                    yvalue2 = results[yvalue2_index]
                    yvalue2 = self.yextractor(yvalue2)

                    comp_label = "{} ({})".format(self.comparison_label, self.vvalue_label_converter(vvalue))

                    dat1.setdefault((key_names, values), {})[(xvalue, comp_label)] = yvalue
                    dat2.setdefault((key_names, values), {})[(xvalue, comp_label)] = yvalue2

                    for (i, (max_comparison_result, min_comparison_result)) in enumerate(zip(max_comparison_results, min_comparison_results)):

                        if data_key in max_comparison_result and data_key in min_comparison_result:

                            (a, b) = max_comparison_result[data_key].get(src_period)
                            dat1.setdefault((key_names, values), {})[(xvalue, self.max_label[i])] = a
                            dat2.setdefault((key_names, values), {})[(xvalue, self.max_label[i])] = b

                            (a, b) = min_comparison_result[data_key].get(src_period)
                            dat1.setdefault((key_names, values), {})[(xvalue, self.min_label[i])] = a
                            dat2.setdefault((key_names, values), {})[(xvalue, self.min_label[i])] = b

                    if baseline_results is not None:
                        (a, b) = baseline_comparison_results[data_key].get(src_period)
                        dat1.setdefault((key_names, values), {})[(xvalue, self.baseline_label)] = a
                        dat2.setdefault((key_names, values), {})[(xvalue, self.baseline_label)] = b


        for ((key_names, key_values), values) in dat1.items():
            self._create_plot(key_names, key_values, values, dat2[(key_names, key_values)])

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
