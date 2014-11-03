# Author: Matthew Bradbury

from __future__ import print_function

import csv
import math
import sys
import numpy

class TableGenerator:

    # The sink distances
    sddata = {
            'SourceCorner': {11: 10, 15: 14, 21: 20, 25: 24},
            'SinkCorner': {11: 10, 15: 14, 21: 20, 25: 24},
            'FurtherSinkCorner': {11: 14, 15: 22, 21: 34, 25: 42},
            'Generic1': {11: 6, 15: 10, 21: 14, 25: 16},
            'Generic2': {11: 12, 15: 20, 21: 32, 25: 40},
            
            'RingTop': {11: 10, 15: 14, 21: 20, 25: 24},
            'RingOpposite': {11: 20, 15: 28, 21: 40, 25: 48},
            'RingMiddle': {11: 20, 15: 28, 21: 40, 25: 48},
            
            'CircleEdges': {11: 14, 15: 18, 21: 26, 25: 30},
            'CircleSourceCentre': {11: 7, 15: 9, 21: 12, 25: 15},
            'CircleSinkCentre': {11: 7, 15: 9, 21: 12, 25: 15},
        }

    def _configuration_rank(self, configuration):
        rank = {
            'SourceCorner': 1, 'SinkCorner': 2, 'FurtherSinkCorner': 3, 'Generic1': 4, 'Generic2': 5,
            
            'RingTop': 6, 'RingOpposite': 7, 'RingMiddle': 8,
            
            'CircleEdges': 9, 'CircleSourceCentre': 10, 'CircleSinkCentre': 11,
            }

        return rank[configuration] if configuration in rank else len(rank) + 1


    def __init__(self):
        self.data = {}

    def analyse(self, result_file):
        def extractAverage(value):
            return float(value.split('(')[0])

        def extractAverageAndSddev(value):
            split = value.split('(')

            mean = float(split[0])
            var = float(split[1].strip(')'))

            return numpy.array((mean, math.sqrt(var)))

        with open(result_file, 'r') as f:

            seenFirst = False
            
            reader = csv.reader(f, delimiter=',')
            
            headers = []
            
            for values in reader:
                # Check if we have seen the first line
                # We do this because we want to ignore it
                if seenFirst:
                    size = int(values[ headers.index('network size') ])
                    srcPeriod = float(values[ headers.index('source period') ])
                    configuration = values[ headers.index('configuration') ]
                    
                    timetaken = extractAverageAndSddev(values[ headers.index('time taken') ])
                    rcv = extractAverageAndSddev(values[ headers.index('received ratio') ]) * 100.0
                    
                    safetyPeriod = float(values[ headers.index('safety period') ])

                    latency = extractAverageAndSddev(values[ headers.index('normal latency') ])
                    
                    self.data \
                        .setdefault(configuration, {}) \
                        .setdefault(size, []) \
                        .append( (srcPeriod, timetaken, safetyPeriod, rcv, latency) )
                else:
                    seenFirst = True
                    headers = values

    def print_table(self, stream=sys.stdout):
        for config in sorted(self.data.keys(), key=self._configuration_rank):
            print('\\begin{table}', file=stream)
            print('\\vspace{-0.35cm}', file=stream)
            print('\\caption{{Safety Periods for the \\textbf{{{}}} configuration}}'.format(config), file=stream)
            print('\\centering', file=stream)
            print('\\begin{tabular}{ | c | c || c || c | c | c || c | }', file=stream)
            print('\\hline', file=stream)
            print('Size & Period & Source-Sink   & Received & Latency   & Average Time    & Safety Period \\tabularnewline', file=stream)
            print('~    & (sec)  & Distance (hop)& (\%)     & (seconds) & Taken (seconds) & (seconds) \\tabularnewline', file=stream)
            print('\\hline', file=stream)
            print('', file=stream)

            for size in sorted(self.data[config].keys()):

                # Sort by srcPeriod
                sortedData = sorted(self.data[config][size], key=lambda x: x[0])

                for (srcPeriod, timeTaken, safetyPeriod, rcv, latency) in sortedData:
                
                    print('{} & {} & {} & {:0.0f} $\pm$ {:0.2f} & {:0.3f} $\pm$ {:0.3f} & {:0.2f} $\pm$ {:0.2f} & {:0.2f} \\tabularnewline'.format(
                            size,
                            srcPeriod,
                            self.sddata[config][size],
                            rcv[0], rcv[1],
                            latency[0], latency[1],
                            timeTaken[0], timeTaken[1],
                            safetyPeriod),
                        file=stream)
                    
                print('\\hline', file=stream)
                print('', file=stream)

            print('\\end{tabular}', file=stream)
            print('\\label{{tab:safety-periods-{}}}'.format(config), file=stream)
            print('\\end{table}', file=stream)
            print('', file=stream)

    def safety_periods(self):
        # type -> configuration -> size -> source rate -> safety period
        result = {}

        for (config, config_list) in self.data.items():
            result[config] = {}
            for (size, size_list) in config_list.items():
                result[config][size] = {}
                for (srcPeriod, timeTaken, safetyPeriod, rcv, latency) in size_list:
                    result[config][size][srcPeriod] = safetyPeriod

        return result
