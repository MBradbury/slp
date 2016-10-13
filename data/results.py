# Author: Matthew Bradbury
from __future__ import division

import ast
import csv
from functools import partial
import math

import numpy

import simulator.common
from simulator import Configuration, SourcePeriodModel

class Results(object):
    def __init__(self, result_file, parameters, results, source_period_normalisation=None, network_size_normalisation=None):
        self.parameter_names = list(parameters)
        self.result_names = list(results)
        self.result_file_name = result_file

        self.data = {}

        self.global_parameter_names = simulator.common.global_parameter_names[:-1]

        for param in self.global_parameter_names:
            setattr(self, self.name_to_attr(param), set())

        self._read_results(result_file, source_period_normalisation, network_size_normalisation)

    def parameters(self):
        return [
            (param, getattr(self, self.name_to_attr(param)))
            for param in self.global_parameter_names
        ]

    @staticmethod
    def name_to_attr(name):
        return name.replace(" ", "_") + "s"

    def _read_results(self, result_file, source_period_normalisation, network_size_normalisation):
        with open(result_file, 'r') as f:

            seen_first = False
            
            reader = csv.reader(f, delimiter='|')
            
            headers = []

            def _get_value_for(name, values):
                if name == 'source period':
                    return SourcePeriodModel.eval_input(values[headers.index(name)]).simple_str()
                else:
                    return values[headers.index(name)]
            
            for values in reader:
                # Check if we have seen the first line
                # We do this because we want to ignore it
                if seen_first:

                    get_value = partial(_get_value_for, values=values)

                    src_period = get_value('source period')

                    if source_period_normalisation is None:
                        source_period = src_period
                    elif source_period_normalisation == "NumSources":

                        config = get_value('configuration')
                        size = int(get_value('network size'))
                        distance = float(get_value('distance'))

                        # Get the source period normalised wrt the number of sources
                        configuration = Configuration.create_specific(config, size, distance, "topology")
                        source_period = str(float(src_period) / len(configuration.source_ids))
                    else:
                        raise RuntimeError("Unknown source period normalisation strategy '{}'".format(source_period_normalisation))

                    if network_size_normalisation is None:
                        pass
                    elif network_size_normalisation == "UseNumNodes":
                        values[headers.index('network size')] = values[headers.index('num nodes')]
                    else:
                        raise RuntimeError("Unknown network size normalisation strategy '{}'".format(network_size_normalisation))

                    table_key = tuple(get_value(name) for name in self.global_parameter_names)

                    params = tuple([self._process(name, headers, values) for name in self.parameter_names])
                    results = tuple([self._process(name, headers, values) for name in self.result_names])

                    for param in self.global_parameter_names:
                        getattr(self, self.name_to_attr(param)).add(get_value(param))

                    self.data.setdefault(table_key, {}).setdefault(source_period, {})[params] = results

                else:
                    seen_first = True
                    headers = values

    def _process(self, name, headers, values):
        try:
            index = headers.index(name)
        except ValueError as ex:
            raise RuntimeError("Unable to read '{}' from the result file '{}'.".format(name, self.result_file_name))

        value = values[index]

        if name == 'captured':
            return float(value) * 100.0
        elif name in {'received ratio', 'paths reached end', 'source dropped'}:
            return self.extract_average_and_stddev(value) * 100.0
        elif name == 'normal latency':
            return self.extract_average_and_stddev(value) * 1000.0
        elif '(' in value and value.endswith(')'):
            return self.extract_average_and_stddev(value)
        elif name in {'approach', 'landmark node', 'order'}:
            return value
        else:
            return ast.literal_eval(value)

    @staticmethod
    def extract_average_and_stddev(value):
        split = value.split('(', 1)

        mean = float(split[0])
        var = float(split[1].strip(')'))

        return numpy.array((mean, math.sqrt(var)))

    def parameter_set(self):
        if 'repeats' not in self.result_names:
            raise RuntimeError("The repeats result must be present in the results ({}).".format(self.result_names))

        result = {}
        for (params, items1) in self.data.items():
            for (period, items2) in items1.items():
                for (key, data) in items2.items():
                    line = list(params)
                    line.append(period)
                    line.extend(key)

                    result[tuple(map(str, line))] = data[self.result_names.index('repeats')]
        
        return result
