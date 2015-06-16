# Author: Matthew Bradbury
from __future__ import division

import csv, math, ast, re, collections

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

        try:
            self._read_results(result_file)
        except BaseException as ex:
            raise RuntimeError("Failure reading {}".format(result_file), ex)

    def _read_results(self, result_file):
        with open(result_file, 'r') as f:

            seen_first = False
            
            reader = csv.reader(f, delimiter='|')
            
            headers = []
            
            for values in reader:
                # Check if we have seen the first line
                # We do this because we want to ignore it
                if seen_first:

                    def _get_value_for(name):
                        return values[headers.index(name)]

                    size = int(_get_value_for('network size'))
                    src_period = SourcePeriodModel.eval_input(_get_value_for('source period')).simple_str()
                    config = _get_value_for('configuration')
                    attacker_model = _get_value_for('attacker model')
                    noise_model = _get_value_for('noise model')
                    communication_model = _get_value_for('communication model')

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

    @staticmethod
    def is_normalised_name(name):
        return name.startswith('norm(') and name.endswith(')')

    @staticmethod
    def get_normalised_names(name):
        if not Results.is_normalised_name(name):
            raise RuntimeError("The name {} is not to be normalised".format(name))

        name = name[len('norm('):-len(')')]

        # Regex from: https://stackoverflow.com/questions/9644784/python-splitting-on-spaces-except-between-certain-characters

        result = tuple(re.split(r",(?=[^()]*(?:\(|$))", name))

        return result

    def _process(self, name, headers, values):

        # Put special variable names here
        if self.is_normalised_name(name):
            (norm_name, div_name) = self.get_normalised_names(name)
            norm_value = self._process(norm_name, headers, values)
            div_value = self._process(div_name, headers, values)

            result = norm_value / div_value

            # Not sure if the stddev can be normalised like this
            # So lets just not do this for now.
            if isinstance(result, (collections.Sequence, numpy.ndarray)):
                # Return just the mean
                return result[0]
            else:
                return result

        index = headers.index(name)
        value = values[index]

        if name == 'captured':
            return float(value) * 100.0
        elif name == 'received ratio':
            return self.extract_average_and_stddev(value) * 100.0
        elif '(' in value:
            return self.extract_average_and_stddev(value)
        elif name == 'approach':
            return value
        else:
            return ast.literal_eval(value)

    @staticmethod
    def extract_average_and_stddev(value):
        split = value.split('(')

        mean = float(split[0])
        var = float(split[1].strip(')'))

        return numpy.array((mean, math.sqrt(var)))
