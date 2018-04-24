
import os

import data.util
from data.graph.versus import Grapher as GrapherBase

class Grapher(GrapherBase):

    def __init__(self, sim_name, output_directory, result_name,
                 xaxis, yaxis, vary, yextractor=None, xextractor=None):

        super(Grapher, self).__init__(
            sim_name, output_directory, result_name, xaxis, yaxis, vary, yextractor, xextractor
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

                    gkey = (xvalue, self.result_label) if self.force_vvalue_label else (xvalue, str(vvalue))

                    dat.setdefault((key_names, values), {})[gkey] = self._value_extractor(yvalue)

                    if baseline_results is not None:
                        baseline_params = tuple(
                            value
                            for (name, value)
                            in zip(simulation_results.parameter_names, params)
                            if name in baseline_results.parameter_names
                        )

                        baseline_res = self.fetch_baseline_result(baseline_results, data_key, src_period, baseline_params)

                        try:
                            baseline_yvalue = baseline_res[ baseline_results.result_names.index(self.yaxis) ]
                        except ValueError:
                            baseline_yvalue = None

                        if baseline_yvalue is not None:
                            if self.force_vvalue_label:
                                baseline_gkey = (xvalue, self.baseline_label)
                            else:
                                vary = self.vary if isinstance(self.vary, tuple) else (self.vary,)

                                if any(v in baseline_results.parameter_names for v in vary):
                                    label = f"{vvalue} ({self.baseline_label})"
                                else:
                                    label = self.baseline_label

                                baseline_gkey = (xvalue, label)

                            dat.setdefault((key_names, values), {})[baseline_gkey] = self._value_extractor(baseline_yvalue)

        return self._build_plots_from_dat(dat)

    def _order_keys(self, keys):
        # Always sort the baseline label last
        skeys = list(sorted(keys))

        if self.baseline_label in skeys:
            skeys.remove(self.baseline_label)
            skeys.append(self.baseline_label)

        return skeys

    def fetch_baseline_result(self, baseline_results, data_key, src_period, baseline_params):
        return baseline_results.data[data_key][src_period][baseline_params]
