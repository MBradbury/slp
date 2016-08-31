
from data.analysis import AnalyzerCommon

class Analyzer(AnalyzerCommon):
    def __init__(self, results_directory):
        super(Analyzer, self).__init__(results_directory, self.results_header(), self.normalised_parameters())

    @staticmethod
    def normalised_parameters():
        return tuple()

    @staticmethod
    def results_header():
        d = AnalyzerCommon.common_results_header()

        AnalyzerCommon.common_results(d)

        d['captured']           = lambda x: str(x.average_of['Captured'])
        d['attacker moves']     = lambda x: AnalyzerCommon._format_results(x, 'AttackerMoves')
        d['attacker distance']  = lambda x: AnalyzerCommon._format_results(x, 'AttackerDistance')
        d['received ratio']     = lambda x: AnalyzerCommon._format_results(x, 'ReceiveRatio')
        d['normal latency']     = lambda x: AnalyzerCommon._format_results(x, 'NormalLatency')
        d['normal']             = lambda x: AnalyzerCommon._format_results(x, 'NormalSent')
        d['dummy normal']       = lambda x: AnalyzerCommon._format_results(x, 'DummyNormalSent')
        d['ssd']                = lambda x: AnalyzerCommon._format_results(x, 'NormalSinkSourceHops')

        d['node was source']    = lambda x: AnalyzerCommon._format_results(x, 'NodeWasSource', allow_missing=True)
        
        d['sent heatmap']       = lambda x: AnalyzerCommon._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: AnalyzerCommon._format_results(x, 'ReceivedHeatMap')

        return d
