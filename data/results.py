# Author: Matthew Bradbury
from __future__ import print_function, division

import ast
import csv
import math
import os.path
import sys

import numpy as np

import data.submodule_loader as submodule_loader

from simulator import Configuration, SourcePeriodModel
import simulator.sim

def literal_eval_with_nan(value):
    if value.lower() == "nan":
        return float('NaN')
    else:
        return ast.literal_eval(value)

to_scale = {'mean', 'std', 'min', 'max', 'sem', '10%', '25%', '50%', '75%', '90%', 'ci95'}

def extract_scaled(value, scale=1):
    value = ast.literal_eval(value.replace('nan', '"NaN"'))
    return {k: (v * scale if k in to_scale else v) if v != "NaN" else float("NaN") for (k, v) in value.items()}

class Results(object):
    def __init__(self, sim_name, result_file, parameters, results, results_filter=None,
                 source_period_normalisation=None, network_size_normalisation=None):
        self.sim_name = sim_name
        self.parameter_names = tuple(parameters)
        self.result_names = tuple(results)
        self.result_file_name = result_file

        self.data = {}

        sim = submodule_loader.load(simulator.sim, sim_name)

        self.global_parameter_names = sim.global_parameter_names[:-1]

        # Create attributes that will store all the parameter value for a given parameter
        for param in self.global_parameter_names:
            setattr(self, self.name_to_attr(param), set())

        self._read_results(result_file, results_filter, source_period_normalisation, network_size_normalisation)

    @property
    def name(self):
        """Get the name of the results.
        This is a horrible hack because the results file is called
        "whatever/[algorithm name]-results.csv". So we can abuse this
        to find out the name of the algorithm this is the results for."""
        return os.path.basename(self.result_file_name).split("-", 1)[0]

    @staticmethod
    def name_to_attr(name):
        return name.replace(" ", "_") + "s"

    def parameters(self):
        return [
            (param, getattr(self, self.name_to_attr(param)))
            for param in self.global_parameter_names
        ]

    def _get_configuration(self, **kwargs):
        args = ('network size', 'distance', 'node id order', 'seed')
        arg_converters = {
            'network size': int,
            'distance': float,
            'seed': int,
        }

        kwargs_copy = {k.replace("_", " "): v for (k,v) in kwargs.items()}

        arg_values = {
            name: arg_converters.get(name, lambda x: x)(kwargs_copy[name])
            for name in args
            if name in kwargs_copy
        }

        return Configuration.create(kwargs['configuration'], arg_values)

    def _normalise_source_period(self, strategy, dvalues):

        src_period = dvalues['source period']

        if strategy is None:
            source_period = src_period

        elif strategy == "NumSources":
            # Get the source period normalised wrt the number of sources
            configuration = self._get_configuration(**dvalues)

            source_period = str(float(src_period) / len(configuration.source_ids))

        else:
            raise RuntimeError(f"Unknown source period normalisation strategy '{strategy}'")

        return source_period

    def _normalise_network_size(self, strategy, dvalues):
        if strategy is None:
            network_size = dvalues['network size']
        elif strategy == "UseNumNodes":
            network_size = dvalues['num nodes']
        else:
            raise RuntimeError(f"Unknown network size normalisation strategy '{strategy}'")

        return network_size


    def _read_results(self, result_path, results_filter, source_period_normalisation, network_size_normalisation):

        print(f"Reading results from {result_path}", file=sys.stderr)

        with open(result_path, 'r') as result_file:

            reader = csv.reader(result_file, delimiter='|', quoting=csv.QUOTE_NONE)
            
            reader_iter = iter(reader)

            # First line contains the headers
            headers = next(reader_iter)
            
            # Remaining lines contain the results
            for values in reader_iter:
                dvalues = dict(zip(headers, values))
                dvalues['source period'] = SourcePeriodModel.eval_input(dvalues['source period']).simple_str()

                source_period = self._normalise_source_period(source_period_normalisation, dvalues)

                if 'network size' in dvalues:
                    dvalues['network size'] = self._normalise_network_size(network_size_normalisation, dvalues)

                table_key = tuple(dvalues[name] for name in self.global_parameter_names)

                params = tuple([self._process(name, dvalues) for name in self.parameter_names])
                results = tuple([self._process(name, dvalues) for name in self.result_names])

                # Check if we should not process this result
                if results_filter is not None:
                    all_params = dict(zip(self.parameter_names, params))
                    all_params.update(dvalues)

                    if results_filter(all_params):
                        #print("Filtering from ", result_path , ": ", all_params)
                        continue

                for param in self.global_parameter_names:
                    getattr(self, self.name_to_attr(param)).add(dvalues[param])

                self.data.setdefault(table_key, {}).setdefault(source_period, {})[params] = results

    def _process(self, name, dvalues):
        try:
            value = dvalues[name]
        except KeyError as ex:
            raise RuntimeError(f"Unable to read '{name}' from the result file '{self.result_file_name}'. Available keys: {dvalues.keys()}")

        if name == 'captured':
            return extract_scaled(value, scale=100.0)
        elif name in {'received ratio', 'paths reached end', 'source dropped', 'average duty cycle'}:
            # Convert from percentage in [0, 1] to [0, 100]
            return extract_scaled(value, scale=100.0)
        elif name == 'normal latency':
            # Convert from seconds to milliseconds
            return extract_scaled(value, scale=1000.0)
        elif 'mean' in value:
            return extract_scaled(value)
        else:
            try:
                return ast.literal_eval(value)
            except (ValueError, SyntaxError):
                # If the value is a string, check if the value is a parameter
                # If it is then just return the string value of the parameter
                if name in self.parameter_names:
                    return value
                else:
                    RuntimeError(f"Unable to parse the string '{value}' for {name}")

    def parameter_set(self):
        if 'repeats' not in self.result_names:
            raise RuntimeError(f"The repeats result must be present in the results ({self.result_names}).")

        repeats_index = self.result_names.index('repeats')

        result = {}
        for (params, items1) in self.data.items():
            for (period, items2) in items1.items():
                for (key, data) in items2.items():

                    line = params + (period,) + key

                    result[line] = data[repeats_index]
        
        return result
