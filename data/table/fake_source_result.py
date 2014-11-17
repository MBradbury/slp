# Author: Matthew Bradbury
from __future__ import print_function

import csv
import math

class ResultTable:

    rank = {
        'SourceCorner': 1, 'SinkCorner': 2, 'FurtherSinkCorner': 3, 'Generic1': 4, 'Generic2': 5,
        'CircleSinkCentre': 6, 'CircleSourceCentre': 7, 'CircleEdges': 8,
        'RingTop': 9, 'RingMiddle': 10, 'RingOpposite': 11,
        }
    
    @staticmethod
    def extractAverageAndSddev(value):
        split = value.split('(')

        mean = float(split[0])
        var = float(split[1].strip(')'))

        return (mean, math.sqrt(var))

    def __init__(self, result_file):
        self.result_file = result_file

    def _read_results(self):
        self.captured = {}
        self.maxFake = {}
        self.received = {}
        self.latency = {}

        #print('Opening: {0}'.format(adinfile))

        self.keys = set()
        self.sizes = set()
        self.sourcePeriods = set()
        self.configurations = set()

        with open(self.result_file, 'r') as f:

            seenFirst = False
            
            reader = csv.reader(f, delimiter=',')
            
            headers = []
            
            for values in reader:
                # Check if we have seen the first line
                # We do this because we want to ignore it
                if seenFirst:

                    size = int(values[ headers.index('network size') ])
                    srcPeriod = float(values[ headers.index('source period') ])
                    config = values[ headers.index('configuration') ]

                    key = (size, srcPeriod, config)

                    self.keys.add(key)
                    self.sizes.add(size)
                    self.sourcePeriods.add(srcPeriod)
                    self.configurations.add(config)
                    
                    # Convert from percentage in the range of [0, 1] to [0, 100]
                    self.captured[key] = float(values[ headers.index('captured') ]) * 100.0

                    self.received[key] = self.extractAverageAndSddev(values[ headers.index('received ratio') ])
                    self.received[key] = (self.received[key][0] * 100.0, self.received[key][1] * 100.0)

                    self.maxFake[key] = self.extractAverageAndSddev(values[ headers.index('fake') ])

                    self.latency[key] = self.extractAverageAndSddev(values[ headers.index('normal latency') ])
                
                else:
                    seenFirst = True
                    headers = values

    def write_tables(self, stream):
        self._read_results()
                    
        print('\\vspace{-0.3cm}', file=stream)

        for configuration in sorted(self.configurations, key=lambda x: self.rank[x]):
            print('\\begin{table}[H]', file=stream)
            print('    \\centering', file=stream)
            print('    \\begin{tabular}{|l|l||l|l|l|l|}', file=stream)
            print('        \\hline', file=stream)
            print('        Size & Source Period & Captured & Fake     & Received & Latency   \\\\', file=stream)
            print('        ~    & (seconds)     & (\\%)    & Messages & (\\%)    & (seconds) \\\\', file=stream)

            currentSize = 0

            for size in sorted(self.sizes):
                for srcPeriod in sorted(self.sourcePeriods):

                    actualkey = (size, srcPeriod, configuration)

                    if currentSize != size:
                        print('        \\hline', file=stream)
                        print('', file=stream)
                        print('        \\multirow{{4}}{{*}}{{{0}}}'.format(size), file=stream)
                        currentSize = size
                    
                    if actualkey in self.keys:
                        print('        ~ & {} & {:.2f} & {:.0f} $\pm$ {:.0f} & {:.1f} $\pm$ {:.1f} & {:.3f} $\pm$ {:.3f} \\\\'.format(
                            float(srcPeriod),
                            self.captured[actualkey],
                            self.maxFake[actualkey][0], self.maxFake[actualkey][1],
                            self.received[actualkey][0], self.received[actualkey][1],
                            self.latency[actualkey][0], self.latency[actualkey][1],
                            ), file=stream)
                    else:
                        print('        ~ & \multicolumn{{5}}{{c}}{{The key {} was not found}} \\\\'.format(
                            actualkey
                            ), file=stream)
                    

            print('        \\hline', file=stream)
            print('    \\end{tabular}', file=stream)
            print('\\caption{{Adaptive results for the {0} configuration}}'.format(configuration), file=stream)
            print('\\end{table}', file=stream)
            print('', file=stream)

            root_path = 'results/Preliminary/Graphs/Versus'
            
            print('\\begin{figure}[H]', file=stream)
            print('    \\vspace{-0.3cm}', file=stream)
            print('    \\centering', file=stream)
            print('    \\subfigure[Capture Rates]{', file=stream)
            print('            \\includegraphics[scale=0.45]{{{0}/PCCaptured/Source-Period/Configuration-{1}/graph}}'.format(root_path, configuration), file=stream)
            print('    }', file=stream)
            print('    \\subfigure[Fake Messages Sent]{', file=stream)
            print('            \\includegraphics[scale=0.45]{{{0}/FakeMessagesSent/Source-Period/Configuration-{1}/graph}}'.format(root_path, configuration), file=stream)
            print('    }', file=stream)
            print('    \\subfigure[Percentage of Messages Received]{', file=stream)
            print('             \\includegraphics[scale=0.45]{{{0}/RcvRatio/Source-Period/Configuration-{1}/graph}}'.format(root_path, configuration), file=stream)
            print('    }', file=stream)
            print('    \\subfigure[Number of Collisions]{', file=stream)
            print('             \\includegraphics[scale=0.45]{{{0}/Collisions/Source-Period/Configuration-{1}/graph}}'.format(root_path, configuration), file=stream)
            print('    }', file=stream)
            print('    \\subfigure[Number of Temporary Fake Sources]{', file=stream)
            print('             \\includegraphics[scale=0.45]{{{0}/NumTFS/Source-Period/Configuration-{1}/graph}}'.format(root_path, configuration), file=stream)
            print('    }', file=stream)
            print('    \\subfigure[Number of Permanent Fake Sources]{', file=stream)
            print('             \\includegraphics[scale=0.45]{{{0}/NumPFS/Source-Period/Configuration-{1}/graph}}'.format(root_path, configuration), file=stream)
            print('    }', file=stream)
            print('    \\subfigure[Normal Message Latency]{', file=stream)
            print('             \\includegraphics[scale=0.45]{{{0}/Latency/Source-Period/Configuration-{1}/graph}}'.format(root_path, configuration), file=stream)
            print('    }', file=stream)
            print('    \\caption{{Results for the {0} configuration}}'.format(configuration), file=stream)
            print('    \\vspace{-0.5cm}', file=stream)
            print('\\end{figure}', file=stream)
            print('\\clearpage', file=stream)
            print('', file=stream)
