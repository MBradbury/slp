# Author: Matthew Bradbury

from __future__ import print_function

import csv
import math
import sys
import numpy

from simulator.Configuration import configuration_rank

class TableGenerator:

    @staticmethod
    def _configuration_rank(configuration):
        return configuration_rank[configuration] if configuration in configuration_rank else len(configuration_rank) + 1

    def __init__(self):
        self.data = {}

    def analyse(self, result_file):
        def extract_average(value):
            return float(value.split('(')[0])

        def extract_average_and_stddev(value):
            split = value.split('(')

            mean = float(split[0])
            var = float(split[1].strip(')'))

            return numpy.array((mean, math.sqrt(var)))

        with open(result_file, 'r') as f:

            seen_first = False
            
            reader = csv.reader(f, delimiter='|')
            
            headers = []
            
            for values in reader:
                # Check if we have seen the first line
                # We do this because we want to ignore it
                if seen_first:
                    size = int(values[ headers.index('network size') ])
                    src_period = float(values[ headers.index('source period') ])
                    configuration = values[ headers.index('configuration') ]
                    
                    time_taken = extract_average_and_stddev(values[ headers.index('time taken') ])
                    rcv = extract_average_and_stddev(values[ headers.index('received ratio') ]) * 100.0

                    safety_period = float(values[ headers.index('safety period') ])

                    latency = extract_average_and_stddev(values[ headers.index('normal latency') ]) * 1000
                    ssd = extract_average_and_stddev(values[ headers.index('ssd') ])
                    
                    self.data \
                        .setdefault(configuration, {}) \
                        .setdefault(size, []) \
                        .append( (src_period, time_taken, safety_period, rcv, latency, ssd) )
                else:
                    seen_first = True
                    headers = values

    def print_table(self, stream=sys.stdout):
        for config in sorted(self.data.keys(), key=self._configuration_rank):
            print('\\begin{table}', file=stream)
            print('\\vspace{-0.35cm}', file=stream)
            print('\\caption{{Safety Periods for the \\textbf{{{}}} configuration}}'.format(config), file=stream)
            print('\\centering', file=stream)
            print('\\begin{tabular}{ | c | c || c | c | c | c || c | }', file=stream)
            print('\\hline', file=stream)
            print('Size & Period & Received & Source-Sink   & Latency   & Average Time    & Safety Period \\tabularnewline', file=stream)
            print('~    & (sec)  & (\%)     & Distance (hop)& (msec)    & Taken (seconds) & (seconds) \\tabularnewline', file=stream)
            print('\\hline', file=stream)
            print('', file=stream)

            for size in sorted(self.data[config].keys()):

                # Sort by src_period
                sorted_data = sorted(self.data[config][size], key=lambda x: x[0])

                for (src_period, time_taken, safety_period, rcv, latency, ssd) in sorted_data:
                
                    print('{} & {} & {:0.0f} $\pm$ {:0.2f} & {:.1f} $\pm$ {:.2f} & {:0.1f} $\pm$ {:0.1f} & {:0.2f} $\pm$ {:0.2f} & {:0.2f} \\tabularnewline'.format(
                            size,
                            src_period,
                            rcv[0], rcv[1],
                            ssd[0], ssd[1],
                            latency[0], latency[1],
                            time_taken[0], time_taken[1],
                            safety_period),
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
                for (src_period, time_taken, safety_period, rcv, latency, ssd) in size_list:
                    result[config][size][src_period] = safety_period

        return result
