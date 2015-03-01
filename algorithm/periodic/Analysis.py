# This file runs the analysis script on the raw data
# and then saves it all in one big csv file.
#
# Author: Matthew Bradbury

from __future__ import print_function

import os, fnmatch

from collections import OrderedDict

from data.analysis import Analyse, AnalysisResults, EmptyFileError

class AnalyseWithOutlierDetection(Analyse):
    def __init__(self, infile):
        super(AnalyseWithOutlierDetection, self).__init__(infile)

    def detect_outlier(self, values):
        # Discard simulations that didn't capture the source
        captured_index = self.headings.index("Captured")
        captured = bool(values[captured_index])

        if not captured:
            raise RuntimeError("Detected outlier, the source was not captured")

        # Discard simulations that took too long
        time_index = self.headings.index("TimeTaken")
        time_taken = float(values[time_index])

        network_size = int(self.opts['network_size'])
        source_period = float(self.opts['source_period'])

        upper_bound = (network_size ** 2) * source_period

        # This can be much stricter than the protectionless upper bound on time.
        # As it can be changed once the simulations have been run.
        if time_taken >= upper_bound:
            raise RuntimeError("Detected outlier, the time taken is {}, upper bound is {}".format(
                time_taken, upper_bound))

class Analyzer:
    def __init__(self, results_directory):
        self.results_directory = results_directory

        d = OrderedDict()
        d['network size']       = lambda x: x.opts['network_size']
        d['configuration']      = lambda x: x.opts['configuration']
        d['source period']      = lambda x: x.opts['source_period']

        def format_results(x, name):
            if name in x.variance_of:
                return "{}({})".format(x.average_of[name], x.variance_of[name])
            else:
                return "{}".format(x.average_of[name])
        
        d['sent']               = lambda x: format_results(x, 'Sent')
        d['received']           = lambda x: format_results(x, 'Received')
        d['captured']           = lambda x: str(x.average_of['Captured'])
        d['attacker moves']     = lambda x: format_results(x, 'AttackerMoves')
        d['attacker distance']  = lambda x: format_results(x, 'AttackerDistance')
        d['received ratio']     = lambda x: format_results(x, 'ReceiveRatio')
        d['normal latency']     = lambda x: format_results(x, 'NormalLatency')
        d['time taken']         = lambda x: format_results(x, 'TimeTaken')
        d['safety period']      = lambda x: str(x.average_of['TimeTaken'] * 2.0)
        d['normal']             = lambda x: format_results(x, 'NormalSent')
        d['ssd']                = lambda x: format_results(x, 'NormalSinkSourceHops')

        d['node was source']    = lambda x: format_results(x, 'NodeWasSource')
        
        d['sent heatmap']       = lambda x: format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: format_results(x, 'ReceivedHeatMap')

        self.values = d

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
                    result = AnalysisResults(AnalyseWithOutlierDetection(path))

                    # Skip 0 length results
                    if len(result.data) == 0:
                        print("Skipping as there is no data.")
                        continue

                    lineData = [f(result) for f in self.values.values()]

                    print("|".join(lineData), file=out)

                except EmptyFileError as e:
                    print(e)
                    
            print('Finished writing {}'.format(summary_file))
