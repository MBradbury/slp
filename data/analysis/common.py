
try:
    import numpy
    mean = numpy.mean
    variance = numpy.var
except:
    def mean(data):
        return sum(data) / len(data)

    # From: http://en.wikipedia.org/wiki/Algorithms_for_calculating_variance#Two-pass_algorithm
    def variance(data):
        variance = 0.0
        average  = mean(data)

        for x in data:
            diff = x - average
            variance += diff * diff

        return variance / (len(data) - 1)

class Analyse:
    def __init__(self, infile):

        self.opts = {}
        self.results = {}
        
        self.headings = []
        self.data = []

        with open(infile) as f:
            for line in f:
        
                # We need to remove the new line at the end of the line
                line = line.strip()

                if '=' in line and len(self.headings) == 0:
                    # We are reading the options so record them
                    opt = line.split('=')

                    self.opts[opt[0]] = opt[1]

                elif line.startswith('#'):
                    # Read the headings
                    self.headings = line[1:].split(',')

                elif ',' in line:
                    # Read the actual data
                    values = line.split(',')

                    self.data.append(values)
                    
                elif ':' in line:
                    # We are reading the options so record them
                    opt = line.split(':')

                    self.results[opt[0]] = opt[1]

                else:
                    pass

    def averageOf(self, header):
        # Find the index that header refers to
        index = self.headings.index(header)

        return mean([float(values[index]) for values in self.data])

    def varianceOf(self, header):
        # Find the index that header refers to
        index = self.headings.index(header)

        return variance([float(values[index]) for values in self.data])
        
    def capturedRuns(self):
        # Find the index that header refers to
        index = self.headings.index('Captured')

        capture = 0.0

        for values in self.data:
            if values[index] == 'true':
                capture += 1.0

        return capture

class AnalysisResults:

    averageOf = {}
    varianceOf = {}

    def __init__(self, analysis):
        for heading in analysis.headings:
            try:
                self.averageOf[heading] = analysis.averageOf(heading)
                self.varianceOf[heading] = analysis.varianceOf(heading)
            except:
                try:
                    del self.averageOf[heading]
                except:
                    pass
                try:
                    del self.varianceOf[heading]
                except:
                    pass

        self.opts = analysis.opts
        self.data = analysis.data
        self.results = analysis.results
