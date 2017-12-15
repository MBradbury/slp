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

        self.result_label = ''
        self.baseline_label = 'Baseline'

        self.force_vvalue_label = False

    def create(self, simulation_results, baseline_results=None):

        # Check assumptions about baseline parameters are not violated
        if baseline_results is not None:
            sim_params = set(simulation_results.parameter_names)
            base_params = set(baseline_results.parameter_names)
            if not base_params.issubset(sim_params):
                raise RuntimeError("The following parameters are in the baseline, but not in the simulation results: {}".format(base_params - sim_params))

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
                    (key_names, values, vvalue) = self.remove_index(key_names, values, self.vary)

                    yvalue = results[ simulation_results.result_names.index(self.yaxis) ]

                    gkey = (xvalue, self.result_label) if self.force_vvalue_label else (xvalue, vvalue)

                    dat.setdefault((key_names, values), {})[gkey] = self._value_extractor(yvalue)

                    if baseline_results is not None:
                        baseline_params = tuple(
                            value
                            for (name, value)
                            in zip(simulation_results.parameter_names, params)
                            if name in baseline_results.parameter_names
                        )

                        baseline_res = baseline_results.data[data_key][src_period][baseline_params]

                        baseline_yvalue = baseline_res[ baseline_results.result_names.index(self.yaxis) ]

                        baseline_gkey = (xvalue, self.baseline_label) if self.force_vvalue_label else (xvalue, "{} ({})".format(vvalue, self.baseline_label))

                        dat.setdefault((key_names, values), {})[baseline_gkey] = self._value_extractor(baseline_yvalue)

        return self._build_plots_from_dat(dat)
