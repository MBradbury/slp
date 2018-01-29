from __future__ import print_function

import os

from collections import defaultdict

import data.util
from data.graph.versus import Grapher as GrapherBase

class Grapher(GrapherBase):
    def __init__(self, sim_name, output_directory,
                 result_name, xaxis, varying, yaxis_label, **kwargs):

        varying_names = [x[0] for x in varying]

        super(Grapher, self).__init__(
            sim_name, output_directory, result_name, xaxis, yaxis_label, varying_names, **kwargs
        )

        self.varying = varying

    def create(self, simulation_results):
        print('Removing existing directories')
        data.util.remove_dirtree(os.path.join(self.output_directory, self.result_name))

        print(f'Creating {self.result_name} graph files')

        dat = {}

        for (data_key, items1) in simulation_results.data.items():
            for (src_period, items2) in items1.items():
                for (params, results) in items2.items():

                    key_names = self._key_names_base + simulation_results.parameter_names

                    values = list(data_key)
                    values.append(src_period)
                    values.extend(params)

                    (key_names, values, xvalue) = self.remove_index(key_names, values, self.xaxis)

                    for (vary, vary_key) in self.varying:
                        yvalue = results[ simulation_results.result_names.index(vary) ]

                        dat.setdefault((key_names, values), {})[(xvalue, vary_key)] = self._value_extractor(yvalue)

        return self._build_plots_from_dat(dat)
