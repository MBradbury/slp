from __future__ import print_function, division

import os

import data.util
from data.graph.versus import Grapher as GrapherBase

class Grapher(GrapherBase):

    def __init__(self, output_directory, result_name,
                 xaxis, yaxis, vary, yextractor=None):

        super(Grapher, self).__init__(
            output_directory, result_name, xaxis, yaxis, vary, yextractor
        )

        self.baseline_label = 'Baseline'

    def create(self, simulation_results, baseline_results=None):
        print('Removing existing directories')
        data.util.remove_dirtree(os.path.join(self.output_directory, self.result_name))

        print('Creating {} graph files'.format(self.result_name))

        dat = {}

        for (data_key, items1) in simulation_results.data.items():
            for (src_period, items2) in items1.items():
                for (params, results) in items2.items():

                    key_names = self._key_names_base + simulation_results.parameter_names

                    values = list(data_key)
                    values.append(src_period)
                    values.extend(params)

                    (key_names, values, xvalue) = self.remove_index(key_names, values, self.xaxis)
                    (key_names, values, vvalue) = self.remove_index(key_names, values, self.vary)

                    yvalue = results[ simulation_results.result_names.index(self.yaxis) ]

                    dat.setdefault((key_names, values), {})[(xvalue, vvalue)] = self._value_extractor(yvalue)

                    if baseline_results is not None:
                        baseline_params = tuple(
                            value
                            for (name, value)
                            in zip(simulation_results.parameter_names, params)
                            if name in baseline_results.parameter_names
                        )

                        baseline_res = baseline_results.data[data_key][src_period][baseline_params]

                        baseline_yvalue = baseline_res[ baseline_results.result_names.index(self.yaxis) ]

                        dat.setdefault((key_names, values), {})[(xvalue, "{}({})".format(self.baseline_label, vvalue))] = self._value_extractor(baseline_yvalue)

        for ((key_names, key_values), values) in dat.items():
            self._create_plot(key_names, key_values, values)

        self._create_graphs(self.result_name)
