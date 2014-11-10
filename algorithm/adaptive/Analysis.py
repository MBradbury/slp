# This file runs the analysis script on the raw data
# and then saves it all in one big csv file.
#
# Author: Matthew Bradbury

import sys
import os
import fnmatch
import math

from data.analysis import Analyse, AnalysisResults

class Analyzer:
    def __init__(self, results_directory):
        self.results_directory = results_directory

    def run(self, summary_file):
        summary_file_path = os.path.join(self.results_directory, summary_file)

        # The output files we need to process
        files = fnmatch.filter(os.listdir(self.results_directory), '*.txt')

        with open(summary_file_path, 'w') as out:

            out.write('{},{},{},{},,{},{},{},{},{},{},{},{},{},{},{},{},{},,{}\n'.format(
                'network size',
                'configuration',
                'algorithm',
                'source period',
                
                'Sent',
                'Received',
                'Collisions',
                'Captured',
                'Received Ratio',
                'Normal Latency',
                'Time',
                'Normal',
                'Away',
                'Choose',
                'Fake',
                'TFS',
                'PFS',
                
                'Heatmap'
                ))

            for infile in files:
                path = os.path.join(self.results_directory, infile)
            
                result = AnalysisResults(Analyse(path))
                
                runs = len(result.data)
            
                print('Analysing {0}'.format(path))

                out.write('{},{},{},{},,{}({}),{}({}),{}({}),{},{}({}),{}({}),{}({}),{}({}),{}({}),{}({}),{}({}),{}({}),{}({}),,{}\n'.format(
                    result.opts['Network Size'],
                    result.opts['Configuration'],
                    result.opts['Algorithm'],
                    result.opts['Source Period'],
                    
                    result.averageOf['Sent'], result.varianceOf['Sent'],
                    result.averageOf['Received'], result.varianceOf['Received'],
                    result.averageOf['Collisions'], result.varianceOf['Collisions'],
                    result.averageOf['Captured'],
                    result.averageOf['Received Ratio'], result.varianceOf['Received Ratio'],
                    result.averageOf['NormalLatency'], result.varianceOf['NormalLatency'],
                    result.averageOf['Time'], result.varianceOf['Time'],
                    result.averageOf['Normal'], result.varianceOf['Normal'],
                    result.averageOf['Away'], result.varianceOf['Away'],
                    result.averageOf['Choose'], result.varianceOf['Choose'],
                    result.averageOf['Fake'], result.varianceOf['Fake'],
                    result.averageOf['TFS'], result.varianceOf['TFS'],
                    result.averageOf['PFS'], result.varianceOf['PFS'],

                    result.results['Sent Map']
                    ))
                    
            print('Finished writing {}'.format(summary_file))
