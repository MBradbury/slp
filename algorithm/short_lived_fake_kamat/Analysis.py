
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

        d['pr(fake)']           = lambda x: x.opts['pr_fake']

        AnalyzerCommon.common_results(d)
        
        d['normal']             = lambda x: AnalyzerCommon._format_results(x, 'NormalSent')
        d['fake']               = lambda x: AnalyzerCommon._format_results(x, 'FakeSent')
        d['tfs']                = lambda x: AnalyzerCommon._format_results(x, 'TFS')
        d['fake to normal']     = lambda x: AnalyzerCommon._format_results(x, 'FakeToNormal')

        d['sent heatmap']       = lambda x: AnalyzerCommon._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: AnalyzerCommon._format_results(x, 'ReceivedHeatMap')

        return d
