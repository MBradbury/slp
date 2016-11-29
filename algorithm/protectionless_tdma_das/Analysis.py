
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

        d['slot period']              = lambda x: x.opts['slot_period']
        d['dissem period']            = lambda x: x.opts['dissem_period']
        d['tdma num slots']           = lambda x: x.opts['tdma_num_slots']
        d['slot assignment interval'] = lambda x: x.opts['slot_assignment_interval']
        d['minimum setup periods']    = lambda x: x.opts['minimum_setup_periods']
        d['pre beacon periods']       = lambda x: x.opts['pre_beacon_periods']
        d['dissem timeout']           = lambda x: x.opts['dissem_timeout']

        AnalyzerCommon.common_results(d)

        d['normal']             = lambda x: AnalyzerCommon._format_results(x, 'NormalSent')
        d['dissem']             = lambda x: AnalyzerCommon._format_results(x, 'DissemSent')

        d['first normal sent time'] = lambda x: AnalyzerCommon._format_results(x, 'FirstNormalSentTime')

        d['node was source']    = lambda x: AnalyzerCommon._format_results(x, 'NodeWasSource', allow_missing=True)
        
        d['sent heatmap']       = lambda x: AnalyzerCommon._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: AnalyzerCommon._format_results(x, 'ReceivedHeatMap')

        return d
