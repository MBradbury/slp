# Author: Matthew Bradbury
from __future__ import division

import csv, math, ast
from functools import partial
import numpy

from simulator import Configuration, SourcePeriodModel

class Results(object):
    def __init__(self, result_file, parameters, results, source_period_normalisation=None):
        self.parameter_names = list(parameters)
        self.result_names = list(results)

        self.data = {}

        from algorithm.common.CommandLineCommon import CLI
        self.global_parameter_names = CLI.global_parameter_names[:-1]

        for param in self.global_parameter_names:
            setattr(self, param.replace(" ", "_") + "s", set())

        self._read_results(result_file, source_period_normalisation)

    def _read_results(self, result_file, source_period_normalisation):
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

                    table_key = tuple(get_value(name) for name in self.global_parameter_names)

                    src_period = get_value('source period')

                    if source_period_normalisation is None:
                        source_period = src_period
                    elif source_period_normalisation == "NumSources":

                        config = get_value('configuration')
                        size = int(get_value('network size'))
                        distance = int(get_value('distance'))

                        # Get the source period normalised wrt the number of sources
                        configuration = Configuration.create_specific(config, size, distance)
                        source_period = str(float(src_period) / len(configuration.source_ids))
                    else:
                        raise RuntimeError("Unknown source period normalisation strategy '{}'".format(source_period_normalisation))


                    params = tuple([self._process(name, headers, values) for name in self.parameter_names])
                    results = tuple([self._process(name, headers, values) for name in self.result_names])

                    for param in self.global_parameter_names:
                        getattr(self, param.replace(" ", "_") + "s").add(get_value(param))

                    self.data.setdefault(table_key, {}).setdefault(source_period, {})[params] = results

                else:
                    seen_first = True
                    headers = values

    def _process(self, name, headers, values):

        #if name.startswith("norm"):
        #    left, right = name[5:-1].split(",", 1)
        #    return self._process(left, headers, values) / self._process(right, headers, values)

        index = headers.index(name)
        value = values[index]

        if name == 'captured':
            return float(value) * 100.0
        elif name in {'received ratio', 'paths reached end', 'source dropped'}:
            return self.extract_average_and_stddev(value) * 100.0
        elif name == 'normal latency':
            return self.extract_average_and_stddev(value) * 1000.0
        elif '(' in value and value.endswith(')'):
            return self.extract_average_and_stddev(value)
        elif name in {'approach', 'landmark node'}:
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
