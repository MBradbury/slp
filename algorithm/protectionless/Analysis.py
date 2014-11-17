# This file runs the analysis script on the raw data
# and then saves it all in one big csv file.
#
# Author: Matthew Bradbury

import sys
import os
import fnmatch
import math

from data.analysis import Analyse, AnalysisResults

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

    def run(self, summary_file):
        summary_file_path = os.path.join(self.results_directory, summary_file)

        # The output files we need to process
        files = fnmatch.filter(os.listdir(self.results_directory), '*.txt')

        with open(summary_file_path, 'w') as out:

            out.write('{},{},{},,{},{},{},{},,{},,{},{},{},{},,{},{}\n'.replace(",", "|").format(
                'network size',
                'source period',
                'configuration',
                
                'time taken',
                'captured',
                'received ratio',
                'normal latency',
                
                'safety period',

                'sent',
                'received',
                'attacker distance',
                'attacker moves',
                #'ssd',

                'sent heatmap',
                'received heatmap'
                ))

            for infile in files:
                path = os.path.join(self.results_directory, infile)

                print('Analysing {0}'.format(path))
            
                result = AnalysisResults(AnalyseWithOutlierDetection(path))

                out.write('{},{},{},,{}({}),{},{}({}),{}({}),,{},,{}({}),{}({}),{},{},,{},{}\n'.replace(",", "|").format(
                    result.opts['network_size'],
                    result.opts['source_period'],
                    result.opts['configuration'],           
                    
                    result.averageOf['TimeTaken'],
                    result.varianceOf['TimeTaken'],

                    result.averageOf['Captured'],
                    
                    result.averageOf['ReceiveRatio'],
                    result.varianceOf['ReceiveRatio'],

                    result.averageOf['NormalLatency'],
                    result.varianceOf['NormalLatency'],
                    
                    result.averageOf['TimeTaken'] * 2.0,

                    result.averageOf['Sent'], result.varianceOf['Sent'],
                    result.averageOf['Received'], result.varianceOf['Received'],
                    result.averageOf['AttackerDistance'],
                    result.averageOf['AttackerMoves'],
                    #result.averageOf['NormalSinkSourceHops'], result.varianceOf['NormalSinkSourceHops'],

                    result.averageOf['SentHeatMap'],
                    result.averageOf['ReceivedHeatMap']
                    ))
                    
            print('Finished writing {}'.format(summary_file))
