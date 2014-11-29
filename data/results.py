# Author: Matthew Bradbury
import csv, math, sys, ast

import numpy

class Results:
    def __init__(self, result_file, parameters, results):
        self.parameter_names = list(parameters)
        self.result_names = list(results)

        self._read_results(result_file)

    def _read_results(self, result_file):

        self.data = {}

        self.sizes = set()
        self.configurations = set()

        with open(result_file, 'r') as f:

            seenFirst = False
            
            reader = csv.reader(f, delimiter='|')
            
            headers = []
            
            for values in reader:
                # Check if we have seen the first line
                # We do this because we want to ignore it
                if seenFirst:

                    size = int(values[ headers.index('network size') ])
                    srcPeriod = float(values[ headers.index('source period') ])
                    config = values[ headers.index('configuration') ]

                    table_key = (size, config)

                    params = tuple([self._process(name, headers, values) for name in self.parameter_names])
                    results = tuple([self._process(name, headers, values) for name in self.result_names])
                
                    self.sizes.add(size)
                    self.configurations.add(config)

                    self.data.setdefault(table_key, {}).setdefault(srcPeriod, {})[params] = results

                else:
                    seenFirst = True
                    headers = values

    def _process(self, name, headers, values):
        index = headers.index(name)
        value = values[index]

        if name == 'captured':
            return float(value) * 100.0
        elif name == 'received ratio':
            return self.extractAverageAndSddev(value) * 100.0
        elif '(' in value:
            return self.extractAverageAndSddev(value)
        elif name == 'technique':
            return value
        else:
            return ast.literal_eval(value)

    @staticmethod
    def extractAverageAndSddev(value):
        split = value.split('(')

        mean = float(split[0])
        var = float(split[1].strip(')'))

        return numpy.array((mean, math.sqrt(var)))
