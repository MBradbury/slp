# This file runs the analysis script on the raw data
# and then saves it all in one big csv file.
#
# Author: Matthew Bradbury

from __future__ import print_function

import os, fnmatch

from collections import OrderedDict

from data.analysis import Analyse, AnalysisResults, EmptyFileError

class Analyzer:
    def __init__(self, results_directory):
        self.results_directory = results_directory

        d = OrderedDict()
        d['network size']       = lambda x: x.opts['network_size']
        d['configuration']      = lambda x: x.opts['configuration']
        d['source period']      = lambda x: x.opts['source_period']
        d['approach']           = lambda x: x.opts['approach']

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
        d['normal']             = lambda x: format_results(x, 'NormalSent')
        d['away']               = lambda x: format_results(x, 'AwaySent')
        d['choose']             = lambda x: format_results(x, 'ChooseSent')
        d['fake']               = lambda x: format_results(x, 'FakeSent')
        d['tfs']                = lambda x: format_results(x, 'TFS')
        d['pfs']                = lambda x: format_results(x, 'PFS')
        d['fake to normal']     = lambda x: format_results(x, 'FakeToNormal')
        d['ssd']                = lambda x: format_results(x, 'NormalSinkSourceHops')

        d['node was source']    = lambda x: format_results(x, 'NodeWasSource')
        d['src change detected'] = lambda x: format_results(x, 'SourceChangeDetected')
        d['detected src change'] = lambda x: format_results(x, 'NodesDetectedSrcChange')

        d['wall time']          = lambda x: format_results(x, 'WallTime')
        d['event count']        = lambda x: format_results(x, 'EventCount')
        
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
                    result = AnalysisResults(Analyse(path))
                    
                    # Skip 0 length results
                    if len(result.data) == 0:
                        print("Skipping as there is no data.")
                        continue

                    lineData = [f(result) for f in self.values.values()]

                    print("|".join(lineData), file=out)

                except EmptyFileError as e:
                    print(e)

            print('Finished writing {}'.format(summary_file))
