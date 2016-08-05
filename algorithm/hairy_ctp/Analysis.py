
from data.analysis import Analyse, AnalysisResults, AnalyzerCommon

from simulator import SourcePeriodModel

class Analyzer(AnalyzerCommon):
    def __init__(self, results_directory):
        super(Analyzer, self).__init__(results_directory, self.results_header(), self.normalised_parameters())

    @staticmethod
    def normalised_parameters():
        return (
            ('Sent', 'TimeTaken'),
            ('NormalSent', 'TimeTaken'),
            ('TimeTaken', 'source_period')
        )

    @staticmethod
    def results_header():
        d = AnalyzerCommon.common_results_header()

        d['sent']               = lambda x: AnalyzerCommon._format_results(x, 'Sent')
        d['received']           = lambda x: AnalyzerCommon._format_results(x, 'Received')
        d['captured']           = lambda x: str(x.average_of['Captured'])
        d['attacker moves']     = lambda x: AnalyzerCommon._format_results(x, 'AttackerMoves')
        d['attacker distance']  = lambda x: AnalyzerCommon._format_results(x, 'AttackerDistance')
        d['received ratio']     = lambda x: AnalyzerCommon._format_results(x, 'ReceiveRatio')
        d['normal latency']     = lambda x: AnalyzerCommon._format_results(x, 'NormalLatency')
        d['time taken']         = lambda x: AnalyzerCommon._format_results(x, 'TimeTaken')
        d['time taken median']  = lambda x: str(x.median_of['TimeTaken'])
        d['safety period']      = lambda x: str(x.average_of['TimeTaken'] * 2.0)
        d['normal']             = lambda x: AnalyzerCommon._format_results(x, 'NormalSent')
        d['ssd']                = lambda x: AnalyzerCommon._format_results(x, 'NormalSinkSourceHops')

        d['node was source']    = lambda x: AnalyzerCommon._format_results(x, 'NodeWasSource')

        d['wall time']          = lambda x: AnalyzerCommon._format_results(x, 'WallTime')
        d['event count']        = lambda x: AnalyzerCommon._format_results(x, 'EventCount')
        
        d['sent heatmap']       = lambda x: AnalyzerCommon._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: AnalyzerCommon._format_results(x, 'ReceivedHeatMap')

        d['norm(sent,time taken)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(Sent,TimeTaken)')
        d['norm(normal,time taken)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(NormalSent,TimeTaken)')
        d['norm(time taken,source period)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(TimeTaken,source_period)')

        return d
