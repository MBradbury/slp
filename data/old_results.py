# Author: Matthew Bradbury
import csv

from data.results import Results

class OldResults(Results):
    def __init__(self, result_file, parameters, results):
        super(OldResults, self).__init__(result_file, parameters, results)

    def _read_results(self, result_file):
        with open(result_file, 'r') as f:

            seen_first = False
           
            reader = csv.reader(f, delimiter=',')

            headers = []

            for values in reader:
                # Check if we have seen the first line
                # We do this because we want to ignore it
                if seen_first:

                    size = int(values[ headers.index('network size') ])
                    src_period = float(values[ headers.index('source period') ])
                    config = values[ headers.index('configuration') ]

                    table_key = (size, config)

                    params = tuple([self._process(name, headers, values) for name in self.parameter_names])
                    results = tuple([self._process(name, headers, values) for name in self.result_names])
                
                    self.sizes.add(size)
                    self.configurations.add(config)

                    self.data.setdefault(table_key, {}).setdefault(src_period, {})[params] = results

                else:
                    seen_first = True
                    headers = values

    def _process(self, name, headers, values):
        index = headers.index(name)
        value = values[index]

        if name == 'configuration' or name == 'network type':
            return value
        else:
            return super()._process(name, headers, values)
