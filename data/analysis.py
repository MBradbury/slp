from __future__ import print_function

from numpy import mean
from numpy import var as variance

import sys, ast, math, os, fnmatch
from collections import Counter

class EmptyFileError(RuntimeError):
    def __init__(self, filename):
        super(EmptyFileError, self).__init__("The file '{}' is empty.".format(filename))

class Analyse(object):
    def __init__(self, infile):

        self.opts = {}
        self.results = {}
        
        self.headings = []
        self.data = []

        with open(infile) as f:
            line_number = 0
            for line in f:

                line_number += 1
        
                # We need to remove the new line at the end of the line
                line = line.strip()

                if '=' in line and len(self.headings) == 0:
                    # We are reading the options so record them
                    opt = line.split('=')

                    self.opts[opt[0]] = opt[1]

                elif line.startswith('#'):
                    # Read the headings
                    self.headings = line[1:].split('|')

                elif '|' in line:
                    try:
                        # Read the actual data
                        values = map(ast.literal_eval, line.split('|'))

                        self.check_consistent(values, line_number)

                        self.detect_outlier(values)

                        self.data.append(values)

                    except RuntimeError as e:
                        print("Unable to process line {} due to {}".format(line_number, e), file=sys.stderr)

                    except ValueError as e:
                        print("Unable to process line {} due to {} ({})".format(line_number, e, line), file=sys.stderr)

                else:
                    print("Unable to parse line {} : '{}'".format(line_number, line))

            if line_number == 0:
                raise EmptyFileError(infile)

    def check_consistent(self, values, line_number):
        """Perform multiple sanity checks on the data generated"""

        # Check that the expected number of values are present
        if len(values) != len(self.headings):
            raise RuntimeError("The number of values {} doesn't equal the number of headings {} on line {}".format(
                len(values), len(self.headings), line_number))

        network_size = int(self.opts['network_size'])
        number_nodes = network_size * network_size

        for (heading, value) in zip(self.headings, values):
            if type(value) is dict:
                
                # Check that there aren't too many nodes
                if len(value) > number_nodes:
                    raise RuntimeError("There are too many nodes in this map {} called {}, when there should be {} maximum.".format(len(value), heading, number_nodes))

                # Check that the node ids are in the right range
                for k in value.keys():
                    if k < 0 or k >= number_nodes:
                        raise RuntimeError("The key {} is invalid for this map it is not between {} and {}".format(k, 0, number_nodes))

        # If captured is set to true, there should be an attacker at the source location
        captured_index = self.headings.index("Captured")
        captured = values[captured_index]

        attacker_distance_index = self.headings.index("AttackerDistance")
        attacker_distance = values[attacker_distance_index]

        if captured != any(v == 0.0 for (k, v) in attacker_distance.items()):
            raise RuntimeError("There is a discrepancy between captured ({}) and the attacker distances {}.".format(captured, attacker_distance))

        # Check NormalLatency is not 0
        latency_index = self.headings.index("NormalLatency")
        latency = values[latency_index]

        if math.isnan(latency):
            raise RuntimeError('The NormalLatency {} is a NaN'.format(latency))

        if latency <= 0:
            raise RuntimeError("The NormalLatency {} is less than or equal to 0.".format(latency))
        


    def detect_outlier(self, values):
        pass

    @staticmethod
    def to_float(value):
        # Convert boolean to floats to allow averaging
        # the number of time the source was captured.
        if value is True:
            return 1.0
        elif value is False:
            return 0.0
        else:
            return float(value)

    def average_of(self, header):
        # Find the index that header refers to
        index = self.headings.index(header)

        if type(self.data[0][index]) is dict:
            return self.dict_mean(index)
        else:
            return mean([self.to_float(values[index]) for values in self.data])

    def variance_of(self, header):
        # Find the index that header refers to
        index = self.headings.index(header)

        if type(self.data[0][index]) is dict:
            raise NotImplementedError()
        else:
            return variance([self.to_float(values[index]) for values in self.data])

    def dict_mean(self, index):
        dict_list = (Counter(values[index]) for values in self.data)

        return { k: float(v) / len(self.data) for (k, v) in dict(sum(dict_list, Counter())).items() }


class AnalysisResults:
    def __init__(self, analysis):
        self.average_of = {}
        self.variance_of = {}
        
        for heading in analysis.headings:
            try:
                self.average_of[heading] = analysis.average_of(heading)
            except (TypeError, RuntimeError) as ex:
                print("Failed to average {}: {}".format(heading, ex), file=sys.stderr)
                #print(traceback.format_exc(), file=sys.stderr)
            
            try:
                self.variance_of[heading] = analysis.variance_of(heading)
            except (TypeError, RuntimeError) as ex:
                print("Failed to find variance {}: {}".format(heading, ex), file=sys.stderr)
                #print(traceback.format_exc(), file=sys.stderr)

        self.opts = analysis.opts
        self.data = analysis.data
        self.results = analysis.results

class AnalyzerCommon(object):
    def __init__(self, results_directory, values):
        self.results_directory = results_directory
        self.values = values

    def analyse_path(self, path):
        return AnalysisResults(Analyse(path))

    def run(self, summary_file):
        summary_file_path = os.path.join(self.results_directory, summary_file)

        # The output files we need to process
        files = fnmatch.filter(os.listdir(self.results_directory), '*.txt')

        with open(summary_file_path, 'w') as out:

            print("|".join(self.values.keys()), file=out)

            for infile in files:
                path = os.path.join(self.results_directory, infile)

                print('Analysing {0}'.format(path))
            
                try:
                    result = self.analyse_path(path)
                    
                    # Skip 0 length results
                    if len(result.data) == 0:
                        print("Skipping as there is no data.")
                        continue

                    lineData = [f(result) for f in self.values.values()]

                    print("|".join(lineData), file=out)

                except EmptyFileError as e:
                    print(e)

            print('Finished writing {}'.format(summary_file))

