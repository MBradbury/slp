# Author: Matthew Bradbury
from __future__ import division

import ast
import csv
import math

import numpy

import simulator.common
from simulator import Configuration, SourcePeriodModel

def _name_to_attr(name):
    return name.replace(" ", "_") + "s"

class Results(object):
    def __init__(self, result_file, parameters, results, source_period_normalisation=None, network_size_normalisation=None):
        self.parameter_names = tuple(parameters)
        self.result_names = tuple(results)
        self.result_file_name = result_file

        self.data = {}

        self.global_parameter_names = simulator.common.global_parameter_names[:-1]

        # Create attributes that will store all the parameter value for a given parameter
        for param in self.global_parameter_names:
            setattr(self, _name_to_attr(param), set())

        self._read_results(result_file, source_period_normalisation, network_size_normalisation)

    def parameters(self):
        return [
            (param, getattr(self, _name_to_attr(param)))
            for param in self.global_parameter_names
        ]

    def _normalise_source_period(self, strategy, dvalues):

        src_period = dvalues['source period']

        if strategy is None:
            source_period = src_period

        elif strategy == "NumSources":
            config = dvalues['configuration']
            size = int(dvalues['network size'])
            distance = float(dvalues['distance'])

            # Get the source period normalised wrt the number of sources
            configuration = Configuration.create_specific(config, size, distance, "topology")
            source_period = str(float(src_period) / len(configuration.source_ids))

        else:
            raise RuntimeError("Unknown source period normalisation strategy '{}'".format(strategy))

        return source_period

    def _normalise_network_size(self, strategy, dvalues):
        if strategy is None:
            network_size = dvalues['network size']
        elif strategy == "UseNumNodes":
            network_size = dvalues['num nodes']
        else:
            raise RuntimeError("Unknown network size normalisation strategy '{}'".format(network_size_normalisation))

        return network_size


    def _read_results(self, result_file, source_period_normalisation, network_size_normalisation):
        with open(result_file, 'r') as f:

            seen_first = False
            
            reader = csv.reader(f, delimiter='|')
            
            headers = []
            
            for values in reader:
                # Check if we have seen the first line
                # We do this because we want to ignore it
                if seen_first:

                    dvalues = dict(zip(headers, values))
                    dvalues['source period'] = SourcePeriodModel.eval_input(dvalues['source period']).simple_str()

                    source_period = self._normalise_source_period(source_period_normalisation, dvalues)

                    values[headers.index('network size')] = self._normalise_network_size(network_size_normalisation, dvalues)

                    table_key = tuple(dvalues[name] for name in self.global_parameter_names)

                    params = tuple([self._process(name, dvalues) for name in self.parameter_names])
                    results = tuple([self._process(name, dvalues) for name in self.result_names])

                    for param in self.global_parameter_names:
                        getattr(self, _name_to_attr(param)).add(dvalues[param])

                    self.data.setdefault(table_key, {}).setdefault(source_period, {})[params] = results

                else:
                    seen_first = True
                    headers = values

    def _process(self, name, dvalues):
        try:
            value = dvalues[name]
        except ValueError as ex:
            raise RuntimeError("Unable to read '{}' from the result file '{}'. Available keys: {}".format(name, self.result_file_name, dvalues.keys()))

        if name == 'captured':
            return float(value) * 100.0
        elif name in {'received ratio', 'paths reached end', 'source dropped'}:
            return self.extract_average_and_stddev(value) * 100.0
        elif name == 'normal latency':
            return self.extract_average_and_stddev(value) * 1000.0
        elif '(' in value and value.endswith(')'):
            return self.extract_average_and_stddev(value)
        else:
            try:
                return ast.literal_eval(value)
            except ValueError:
                # If the value is a string, check if the value is a parameter
                # If it is then just return the string value of the parameter
                if name in self.parameter_names:
                    return value
                else:
                    raise

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
