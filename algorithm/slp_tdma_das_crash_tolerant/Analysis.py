
from data.analysis import AnalyzerCommon

algorithm_module = __import__(__package__, globals(), locals(), ['object'], -1)

class Analyzer(AnalyzerCommon):
    def __init__(self, results_directory):
        super(Analyzer, self).__init__(results_directory, self.results_header(), self.normalised_parameters())

    @staticmethod
    def normalised_parameters():
        return (
            ('Sent', 'TimeTaken'),
            (('Sent', 'TimeTaken'), 'num_nodes'),
        )

    @staticmethod
    def results_header():
        d = AnalyzerCommon.common_results_header(algorithm_module.local_parameter_names)

        AnalyzerCommon.common_results(d)

        d['normal']             = lambda x: AnalyzerCommon._format_results(x, 'NormalSent')
        d['empty normal']       = lambda x: AnalyzerCommon._format_results(x, 'EmptyNormalSent')
        d['dissem']             = lambda x: AnalyzerCommon._format_results(x, 'DissemSent')
        d['search']             = lambda x: AnalyzerCommon._format_results(x, 'SearchSent')
        d['change']             = lambda x: AnalyzerCommon._format_results(x, 'ChangeSent')
        d['crash']              = lambda x: AnalyzerCommon._format_results(x, 'CrashSent')

        d['node was source']    = lambda x: AnalyzerCommon._format_results(x, 'NodeWasSource', allow_missing=True)

        d['sent heatmap']       = lambda x: AnalyzerCommon._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: AnalyzerCommon._format_results(x, 'ReceivedHeatMap')

        d['norm(sent,time taken)'] = lambda x: AnalyzerCommon._format_results(x, 'norm(Sent,TimeTaken)')
        d['norm(norm(sent,time taken),network size)'] = lambda x: AnalyzerCommon._format_results(x, 'norm(norm(Sent,TimeTaken),num_nodes)')

        d['control sent']       = lambda x: str(x.average_of['SearchSent'] + x.average_of['ChangeSent'] + x.average_of['CrashSent'])
        d['path sent']          = lambda x: str(x.average_of['SearchSent'] + x.average_of['ChangeSent'])
        d['overhead']           = lambda x: str((x.average_of['SearchSent'] + x.average_of['ChangeSent'] + x.average_of['CrashSent'])/x.average_of['NormalSent'])

        return d
