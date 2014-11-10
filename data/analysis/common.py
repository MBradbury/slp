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

                    self.check_consistent(values, lineNumber)

                    self.data.append(values)

                else:
                    print("Unable to parse: {}".format(line))

                lineNumber += 1

    def check_consistent(self, values, lineNumber):
        if len(values) != len(self.headings):
            raise RuntimeError("The number of values {} doesn't equal the number of headings {} on line {}".format(
                len(values), len(self.headings), lineNumber))


    def averageOf(self, header):
        # Find the index that header refers to
        index = self.headings.index(header)

        if "{" in self.data[0][index]:
            return self.dictMean(index)
        else:
            return mean([float(values[index]) for values in self.data])

    def varianceOf(self, header):
        # Find the index that header refers to
        index = self.headings.index(header)

        if "{" in self.data[0][index]:
            raise NotImplementedError()
        else:
            return variance([float(values[index]) for values in self.data])

    def dictMean(self, index):
        dictList = [Counter(ast.literal_eval(values[index])) for values in self.data]

        return { k: float(v) / len(dictList) for (k, v) in dict(sum(dictList, Counter())).items() }
        
    def capturedRuns(self):
        # Find the index that header refers to
        index = self.headings.index('Captured')

        capture = 0.0

        for values in self.data:
            if values[index] == 'true':
                capture += 1.0

        return capture

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
