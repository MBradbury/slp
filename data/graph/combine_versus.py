from __future__ import print_function

import os

from collections import defaultdict

import data.util
from data.graph.versus import Grapher as GrapherBase

class Grapher(GrapherBase):
    def __init__(self, output_directory,
                 result_name, xaxis, yaxis, vary, combine, combine_function, yextractor=None):

        super(Grapher, self).__init__(
            output_directory, result_name, xaxis, yaxis, vary, yextractor
        )

        self.combine = combine
        self.combine_function = combine_function

    def create(self, simulation_results):
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

                    cvalues = []
                    for vary in self.combine:
                        (key_names, values, cvalue) = self.remove_index(key_names, values, vary)
                        cvalues.append(cvalue)
                    cvalues = tuple(cvalues)

                    yvalue = results[ simulation_results.result_names.index(self.yaxis) ]

                    dat.setdefault((key_names, values), {}).setdefault((xvalue, vvalue), {})[cvalues] = self.yextractor(yvalue)

        
        newdat = defaultdict(dict)

        # Extract the data we want to display
        for ((key_names, values), items1) in dat.items():
            for ((xvalue, vvalue), items2) in items1.items():

                results = tuple(items2.values())

                newdat[(key_names, values)][(xvalue, vvalue)] = self.combine_function(results)
                    
        return self._build_plots_from_dat(newdat)
