# Author: Matthew Bradbury
from __future__ import division

import csv, math, ast
from functools import partial
import numpy

from simulator import SourcePeriodModel

class Results(object):
    def __init__(self, result_file, parameters, results):
        self.parameter_names = list(parameters)
        self.result_names = list(results)

        self.data = {}

        self.sizes = set()
        self.configurations = set()
        self.attacker_models = set()
        self.noise_models = set()
        self.communication_models = set()

        self._read_results(result_file)

    def _read_results(self, result_file):
        with open(result_file, 'r') as f:

            seen_first = False
            
            reader = csv.reader(f, delimiter='|')
            
            headers = []

            def _get_value_for(name, values):
                return values[headers.index(name)]
            
            for values in reader:
                # Check if we have seen the first line
                # We do this because we want to ignore it
                if seen_first:

                    get_value = partial(_get_value_for, values=values)

                    size = int(get_value('network size'))
                    src_period = SourcePeriodModel.eval_input(get_value('source period')).simple_str()
                    config = get_value('configuration')
                    attacker_model = get_value('attacker model')
                    noise_model = get_value('noise model')
                    communication_model = get_value('communication model')

                    table_key = (size, config, attacker_model, noise_model, communication_model)

                    params = tuple([self._process(name, headers, values) for name in self.parameter_names])
                    results = tuple([self._process(name, headers, values) for name in self.result_names])

                    self.sizes.add(size)
                    self.configurations.add(config)
                    self.attacker_models.add(attacker_model)
                    self.noise_models.add(noise_model)
                    self.communication_models.add(communication_model)

                    self.data.setdefault(table_key, {}).setdefault(src_period, {})[params] = results

                else:
                    seen_first = True
                    headers = values

    def _process(self, name, headers, values):           

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
        split = value.split('(')

        mean = float(split[0])
        var = float(split[1].strip(')'))

        return numpy.array((mean, math.sqrt(var)))
