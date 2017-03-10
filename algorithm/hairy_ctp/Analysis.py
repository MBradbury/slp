
from data.analysis import AnalyzerCommon

algorithm_module = __import__(__package__, globals(), locals(), ['object'], -1)

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
        d = AnalyzerCommon.common_results_header(algorithm_module.local_parameter_names)

        AnalyzerCommon.common_results(d)

        d['normal']             = lambda x: AnalyzerCommon._format_results(x, 'NormalSent')

        d['node was source']    = lambda x: AnalyzerCommon._format_results(x, 'NodeWasSource')

        d['sent heatmap']       = lambda x: AnalyzerCommon._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: AnalyzerCommon._format_results(x, 'ReceivedHeatMap')

        d['norm(sent,time taken)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(Sent,TimeTaken)')
        d['norm(normal,time taken)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(NormalSent,TimeTaken)')
        d['norm(time taken,source period)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(TimeTaken,source_period)')

        return d
