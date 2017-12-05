
from data.analysis import AnalyzerCommon

algorithm_module = __import__(__package__, globals(), locals(), ['object'])

class Analyzer(AnalyzerCommon):
    def __init__(self, results_directory):
        super(Analyzer, self).__init__(results_directory, self.results_header(), self.normalised_parameters(), self.filtered_parameters())

    @staticmethod
    def normalised_parameters():
        return (
            ('Sent', 'TimeTaken'),
            ('NormalSent', 'TimeTaken'),

            ('energy_impact', 'num_nodes'),
            (('energy_impact', 'num_nodes'), 'TimeTaken'),
            ('daily_allowance_used', '1'),
        )

    @staticmethod
    def filtered_parameters():
        return (
            ('FailedAvoidSink', 'Captured'),
        )

    @staticmethod
    def results_header():
        d = AnalyzerCommon.common_results_header(algorithm_module.local_parameter_names)

        AnalyzerCommon.common_results(d)

        d['normal']             = lambda x: AnalyzerCommon._format_results(x, 'NormalSent')
        d['away']               = lambda x: AnalyzerCommon._format_results(x, 'AwaySent')
        d['beacon']             = lambda x: AnalyzerCommon._format_results(x, 'BeaconSent')
        d['poll']               = lambda x: AnalyzerCommon._format_results(x, 'PollSent')

        d['failed rtx']         = lambda x: AnalyzerCommon._format_results(x, 'FailedRtx')
        d['failed avoid sink']  = lambda x: AnalyzerCommon._format_results(x, 'FailedAvoidSink')

        d['failed avoid sink when captured']  = lambda x: AnalyzerCommon._format_results(x, 'filtered(FailedAvoidSink,Captured)')

        #d['node was source']    = lambda x: AnalyzerCommon._format_results(x, 'NodeWasSource')

        d['sent heatmap']       = lambda x: AnalyzerCommon._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: AnalyzerCommon._format_results(x, 'ReceivedHeatMap')

        d['norm(sent,time taken)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(Sent,TimeTaken)')
        d['norm(normal,time taken)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(NormalSent,TimeTaken)')

        d['energy impact per node']   = lambda x: AnalyzerCommon._format_results(x, 'norm(energy_impact,num_nodes)')
        d['energy impact per node per second']   = lambda x: AnalyzerCommon._format_results(x, 'norm(norm(energy_impact,num_nodes),TimeTaken)')
        d['energy allowance used'] = lambda x: AnalyzerCommon._format_results(x, 'norm(daily_allowance_used,1)')

        return d
