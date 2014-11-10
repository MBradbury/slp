# This file runs the analysis script on the raw data
# and then saves it all in one big csv file.
#
# Author: Matthew Bradbury

import sys
import os
import fnmatch
import math

from .common import *

class Analyzer:
    def __init__(self, results_directory):
        self.results_directory = results_directory

    def run(self, summary_file):
        summary_file_path = os.path.join(self.results_directory, summary_file)

        # The output files we need to process
        files = fnmatch.filter(os.listdir(self.results_directory), '*.txt')

        with open(summary_file_path, 'w') as out:

            out.write('{},{},{},,{},{},{},{},,{},,{},{}\n'.replace(",", "|").format(
                'network size',
                'source period',
                'configuration',
                
                'time taken',
                'captured',
                'received ratio',
                'normal latency',
                
                'safety period',

                'sent heatmap',
                'received heatmap'
                ))

            for infile in files:
                path = os.path.join(self.results_directory, infile)

                print('Analysing {0}'.format(path))
            
                result = AnalysisResults(Analyse(path))

                out.write('{},{},{},,{}({}),{},{}({}),{}({}),,{},,{},{}\n'.replace(",", "|").format(
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

                    result.averageOf['SentHeatMap'],
                    result.averageOf['ReceivedHeatMap']
                    ))
                    
            print('Finished writing {}'.format(summary_file))
