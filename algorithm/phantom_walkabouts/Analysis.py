
from data.analysis import AnalyzerCommon

class Analyzer(AnalyzerCommon):
    def __init__(self, results_directory):
        super(Analyzer, self).__init__(results_directory, self.results_header(), self.normalised_parameters())

    @staticmethod
    def normalised_parameters():
        return [
            ('Sent', 'TimeTaken'),
            (('Sent', 'TimeTaken'), 'num_nodes'),
        ]

    @staticmethod
    def results_header():
        d = AnalyzerCommon.common_results_header()

        d['short walk length']  = lambda x: x.opts['short_walk_length']
        d['long walk length']   = lambda x: x.opts['long_walk_length']
        d['short count']        = lambda x: x.opts['short_count']
        d['long count']         = lambda x: x.opts['long_count']
        d['order']              = lambda x: x.opts['order']
        d['direction bias']     = lambda x: x.opts['direction_bias']
        d['wait before short']  = lambda x: x.opts['wait_before_short']

        AnalyzerCommon.common_results(d)
        
        d['normal']             = lambda x: AnalyzerCommon._format_results(x, 'NormalSent')
        d['away']               = lambda x: AnalyzerCommon._format_results(x, 'AwaySent')
        d['beacon']             = lambda x: AnalyzerCommon._format_results(x, 'BeaconSent')

        d['paths reached end']  = lambda x: AnalyzerCommon._format_results(x, 'PathsReachedEnd')
        d['source dropped']     = lambda x: AnalyzerCommon._format_results(x, 'SourceDropped')
        d['path dropped']       = lambda x: AnalyzerCommon._format_results(x, 'PathDropped', allow_missing=True)
        d['path dropped length']= lambda x: AnalyzerCommon._format_results(x, 'PathDroppedLength', allow_missing=True)

        d['sent heatmap']       = lambda x: AnalyzerCommon._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: AnalyzerCommon._format_results(x, 'ReceivedHeatMap')

        d['norm(sent,time taken)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(Sent,TimeTaken)')
        d['norm(norm(sent,time taken),network size)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(norm(Sent,TimeTaken),num_nodes)')

        return d
