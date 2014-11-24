# This file runs the analysis script on the raw data
# and then saves it all in one big csv file.
#
# Author: Matthew Bradbury

import sys
import os
import fnmatch
import math

from data.analysis import Analyse, AnalysisResults, EmptyFileError

class Analyzer:
    def __init__(self, results_directory):
        self.results_directory = results_directory

    def run(self, summary_file):
        summary_file_path = os.path.join(self.results_directory, summary_file)

        # The output files we need to process
        files = fnmatch.filter(os.listdir(self.results_directory), '*.txt')

        with open(summary_file_path, 'w') as out:

            out.write('{},{},{},{},,{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},,{},{}\n'.replace(",", "|").format(
                'network size',
                'configuration',
                'source period',
                'technique',
                
                'sent',
                'received',
                'captured',
                'attacker moves',
                'attacker distance',
                'received ratio',
                'normal latency',
                'time taken',
                'normal',
                'away',
                'choose',
                'fake',
                'tfs',
                'pfs',
                'fake to normal',
                'ssd',
                
                'sent heatmap',
                'received heatmap'
                ))

            for infile in files:
                path = os.path.join(self.results_directory, infile)
            
                try:
                    result = AnalysisResults(Analyse(path))
                    
                    print('Analysing {0}'.format(path))

                    out.write('{},{},{},{},,{}({}),{}({}),{},{},{},{}({}),{}({}),{}({}),{}({}),{}({}),{}({}),{}({}),{}({}),{}({}),{}({}),{}({}),,{},{}\n'.replace(",", "|").format(
                        result.opts['network_size'],
                        result.opts['configuration'],
                        result.opts['source_period'],
                        result.opts['technique'],
                        
                        result.averageOf['Sent'], result.varianceOf['Sent'],
                        result.averageOf['Received'], result.varianceOf['Received'],
                        #result.averageOf['Collisions'], result.varianceOf['Collisions'],
                        result.averageOf['Captured'],
                        result.averageOf['AttackerMoves'],
                        result.averageOf['AttackerDistance'],
                        result.averageOf['ReceiveRatio'], result.varianceOf['ReceiveRatio'],
                        result.averageOf['NormalLatency'], result.varianceOf['NormalLatency'],
                        result.averageOf['TimeTaken'], result.varianceOf['TimeTaken'],
                        result.averageOf['NormalSent'], result.varianceOf['NormalSent'],
                        result.averageOf['AwaySent'], result.varianceOf['AwaySent'],
                        result.averageOf['ChooseSent'], result.varianceOf['ChooseSent'],
                        result.averageOf['FakeSent'], result.varianceOf['FakeSent'],
                        result.averageOf['TFS'], result.varianceOf['TFS'],
                        result.averageOf['PFS'], result.varianceOf['PFS'],
                        result.averageOf['FakeToNormal'], result.varianceOf['FakeToNormal'],
                        result.averageOf['NormalSinkSourceHops'], result.varianceOf['NormalSinkSourceHops'],

                        result.averageOf['SentHeatMap'],
                        result.averageOf['ReceivedHeatMap']
                        ))

                except EmptyFileError as e:
                    print(e)

            print('Finished writing {}'.format(summary_file))
