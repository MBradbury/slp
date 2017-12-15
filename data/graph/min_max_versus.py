from __future__ import print_function

from collections import defaultdict
import os

import simulator.common

import data.util
from data.graph.versus import Grapher as GrapherBase

import numpy as np

class Grapher(GrapherBase):
    def __init__(self, output_directory,
                 result_name, xaxis, yaxis, vary, yextractor=None, key_equivalence=None):

        super(Grapher, self).__init__(
            output_directory, result_name, xaxis, yaxis, vary, yextractor
        )

        self.max_label = 'Maximum'
        self.min_label = 'Minimum'
        self.min_max_same_label = 'Same'
        self.comparison_label = 'Comparison'
        self.baseline_label = 'Baseline'

        self.vvalue_label_converter = str

        self.allow_missing_comparison = False

        self.key_equivalence = key_equivalence

    def create(self, comparison_results, actual_results, baseline_results=None):
        print('Removing existing directories')
        data.util.remove_dirtree(os.path.join(self.output_directory, self.result_name))

        print(f'Creating {self.result_name} graph files')

        dat = {}

        min_comparison_results = []
        max_comparison_results = []
        baseline_comparison_results = {}

        # Handle the case where a single comparison result is provided
        if not isinstance(comparison_results, (list, tuple)):
            comparison_results = [comparison_results]

        if not isinstance(self.max_label, (list, tuple)):
            self.max_label = [self.max_label]

        if not isinstance(self.min_label, (list, tuple)):
            self.min_label = [self.min_label]

        if not isinstance(self.min_max_same_label, (list, tuple)):
            self.min_max_same_label = [self.min_max_same_label]

        for comparison_result in comparison_results:

            min_comparison_result = {}
            max_comparison_result = {}

            # Find the min and max results over all parameter combinations 
            for (data_key, items1) in comparison_result.data.items():
                for (src_period, items2) in items1.items():

                    local_min = {}
                    local_max = {}

                    for (params, results) in items2.items():

                        (params_names, params, xvalue) = self.remove_index(
                            comparison_result.parameter_names, params, self.xaxis, allow_missing=True)

                        yvalue_index = comparison_result.result_names.index(self.yaxis)
                        yvalue = results[yvalue_index]
                        yvalue = self._value_extractor(yvalue)

                        local_min[xvalue] = yvalue if xvalue not in local_min else min(local_min[xvalue], yvalue)
                        local_max[xvalue] = yvalue if xvalue not in local_max else max(local_max[xvalue], yvalue)

                    for xvalue in local_min:
                        min_comparison_result.setdefault(data_key, {}).setdefault(src_period, {})[xvalue] = local_min[xvalue]
                        max_comparison_result.setdefault(data_key, {}).setdefault(src_period, {})[xvalue] = local_max[xvalue]

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

        min_max_merge_consider = defaultdict(set)

        xvalues = set()

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

                    xvalues.add(xvalue)

                    key_names = tuple(key_names)
                    values = tuple(values)

                    yvalue_index = actual_results.result_names.index(self.yaxis)
                    yvalue = results[yvalue_index]
                    yvalue = self._value_extractor(yvalue)

                    comp_label = "{} ({})".format(self.comparison_label, self.vvalue_label_converter(vvalue))

                    dat.setdefault((key_names, values), {})[(xvalue, comp_label)] = yvalue

                    for (i, (max_comparison_result, min_comparison_result)) in enumerate(zip(max_comparison_results, min_comparison_results)):

                        comparison_data_key = self._get_key_in_comparison(data_key, max_comparison_result, min_comparison_result)

                        if comparison_data_key is not None:

                            max_value = self._get_compairson_result(max_comparison_result, comparison_data_key, src_period, xvalue)
                            min_value = self._get_compairson_result(min_comparison_result, comparison_data_key, src_period, xvalue)

                            dat.setdefault((key_names, values), {})[(xvalue, self.max_label[i])] = max_value

                            dat.setdefault((key_names, values), {})[(xvalue, self.min_label[i])] = min_value

                            try:
                                if np.isclose(min_value, max_value):
                                    min_max_merge_consider[(key_names, values, self.max_label[i], self.min_label[i], i)].add(xvalue)
                            except TypeError:
                                # We can't compare default values that are strings,
                                # so just skip trying to merge these ones
                                pass

                        else:
                            print("Not processing {} as it is not in the min/max data:".format(data_key))
                            for key in sorted(max_comparison_result):
                                print("\t{}".format(key))

                    if baseline_results is not None:
                        dat.setdefault((key_names, values), {})[(xvalue, self.baseline_label)] = baseline_comparison_results[data_key].get(src_period)

        # If every min/max value are close to each other, then remove both and replace with one "same" line
        for ((key_names, values, max_label, min_label, i), this_xvalues) in min_max_merge_consider.items():

            # If all xvalues are the same
            if this_xvalues == xvalues:
                local_dat = dat[(key_names, values)]

                # The values to add using the same label
                same_to_add = {
                    (xvalue, self.min_max_same_label[i]): max_value
                    for (xvalue, max_label_i), max_value in local_dat.items()
                    if max_label == max_label_i
                }

                # The values without min or max results
                local_dat = {
                    (xvalue, label): value
                    for (xvalue, label), value in local_dat.items()
                    if label not in (max_label, min_label)
                }

                # Add back in the same labels
                local_dat.update(same_to_add)

                # Update dat
                dat[(key_names, values)] = local_dat

        return self._build_plots_from_dat(dat)

    def _get_key_in_comparison(self, data_key, max_comparison_result, min_comparison_result):
        # Try the simple case first
        if data_key in max_comparison_result and data_key in min_comparison_result:
            return data_key

        # No key equivalences, so we can't do anything
        if self.key_equivalence is None:
            return None

        # Right we need to look at the key equivalences then

        global_parameter_names = simulator.common.global_parameter_names

        keys_to_try = []

        for (global_param, replacements) in self.key_equivalence.items():
            global_param_index = global_parameter_names.index(global_param)

            for (search, replace) in replacements.items():
                if data_key[global_param_index] == search:

                    new_key = data_key[:global_param_index] + (replace,) + data_key[global_param_index+1:]

                    keys_to_try.append(new_key)

        # Try each of the possible combinations
        for key_attempt in keys_to_try:
            if key_attempt in max_comparison_result and key_attempt in min_comparison_result:
                print("Found {} so using it instead of {}".format(key_attempt, data_key))
                return key_attempt

        return None

    def _get_compairson_result(self, comparison_result, data_key, src_period, xvalue):
        res = comparison_result[data_key].get(src_period)

        # If no result for the source period, allow it to be missing
        if res is None:
            return None

        if xvalue in res:
            return res[xvalue]
        else:
            try:
                return res[tuple()]
            except KeyError:
                if self.allow_missing_comparison:
                    return self.missing_value_string
                else:
                    raise KeyError("Unable to find {} or tuple() in {} when looking for an xvalue with the key {}".format(
                        xvalue, set(res.keys()), data_key))

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
