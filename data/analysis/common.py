from __future__ import print_function

from numpy import mean
from numpy import var as variance

import sys, ast
from collections import Counter

class Analyse:
    def __init__(self, infile):

        self.opts = {}
        self.results = {}
        
        self.headings = []
        self.data = []

        with open(infile) as f:
            lineNumber = 1
            for line in f:
        
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
                    # Read the actual data
                    values = line.split('|')

                    try:
                        self.check_consistent(values, lineNumber)

                        self.check_outlier(values, lineNumber)

                        self.data.append(values)
                    except RuntimeError as e:
                        print("Unable to process line {} due to {}".format(lineNumber, e), file=sys.stderr)

                else:
                    print("Unable to parse line {} : '{}'".format(lineNumber, line))

                lineNumber += 1

    def check_consistent(self, values, lineNumber):
        if len(values) != len(self.headings):
            raise RuntimeError("The number of values {} doesn't equal the number of headings {} on line {}".format(
                len(values), len(self.headings), lineNumber))

        for (heading, value) in zip(self.headings, values):
            if value.startswith('{'):
                # Check that the map format is valid
                try:
                    d = ast.literal_eval(value)
                except SyntaxError as e:
                    raise RuntimeError("The value for {} could not be parsed".format(heading), e)

                network_size = int(self.opts['network_size'])
                number_nodes = network_size * network_size

                # Check that there aren't too many nodes
                if len(d) > number_nodes:
                    raise RuntimeError("There are too many nodes in this map {}, when there should be {} maximum.".format(len(d), number_nodes))

                # Check that the node ids are in the right range
                for k in d.keys():
                    if k < 0 or k >= number_nodes:
                        raise RuntimeError("The key {} is invalid for this map it is not between {} and {}".format(k, 0, number_nodes))

    def check_outlier(self, values, lineNumber):
        index = self.headings.index("TimeTaken")

        time_taken = float(values[index])

        if time_taken > 500:
            raise RuntimeError("Detected outlier, the time taken is {}".format(time_taken))

    @staticmethod
    def to_float(value):

        value_lit = ast.literal_eval(value)

        if value_lit is True:
            return 1.0
        elif value_lit is False:
            return 0.0
        else:
            return float(value)

    def averageOf(self, header):
        # Find the index that header refers to
        index = self.headings.index(header)

        if "{" in self.data[0][index]:
            return self.dictMean(index)
        else:
            return mean([self.to_float(values[index]) for values in self.data])

    def varianceOf(self, header):
        # Find the index that header refers to
        index = self.headings.index(header)

        if "{" in self.data[0][index]:
            raise NotImplementedError()
        else:
            return variance([self.to_float(values[index]) for values in self.data])

    def dictMean(self, index):
        dictList = [Counter(ast.literal_eval(values[index])) for values in self.data]

        return { k: float(v) / len(dictList) for (k, v) in dict(sum(dictList, Counter())).items() }


class AnalysisResults(object):
    def __init__(self, analysis):
        self.averageOf = {}
        self.varianceOf = {}
        
        for heading in analysis.headings:
            try:
                self.averageOf[heading] = analysis.averageOf(heading)
            except Exception as e:
                try:
                    del self.averageOf[heading]
                except:
                    pass
                print("Failed to average {}: {}".format(heading, e), file=sys.stderr)
            try:
                self.varianceOf[heading] = analysis.varianceOf(heading)
            except Exception as e:
                try:
                    del self.varianceOf[heading]
                except:
                    pass
                print("Failed to find variance {}: {}".format(heading, e), file=sys.stderr)

        self.opts = analysis.opts
        self.data = analysis.data
        self.results = analysis.results
