
from data.analysis import AnalyzerCommon

algorithm_module = __import__(__package__, globals(), locals(), ['object'], -1)

class Analyzer(AnalyzerCommon):
    def __init__(self, results_directory):
        super(Analyzer, self).__init__(results_directory, self.results_header(), self.normalised_parameters(), self.filtered_parameters())

    @staticmethod
    def normalised_parameters():
        return (
            ('Sent', 'TimeTaken'),
            (('Sent', 'TimeTaken'), 'num_nodes'),
            (('Sent', 'TimeTaken'), 'source_rate'),
            ((('Sent', 'TimeTaken'), 'num_nodes'), 'source_rate'),

            ('FakeSent', 'TimeTaken'),
            (('FakeSent', 'TimeTaken'), 'num_nodes'),
            (('FakeSent', 'TimeTaken'), 'source_rate'),
            ((('FakeSent', 'TimeTaken'), 'num_nodes'), 'source_rate'),

            ('NormalSent', 'TimeTaken'),

            ('energy_impact', '1'),
            ('energy_impact', 'num_nodes'),
            (('energy_impact', 'num_nodes'), 'TimeTaken'),
            ('daily_allowance_used', '1'),
        )

    @staticmethod
    def filtered_parameters():
        return (
            ('FakeNodesAtEnd', 'Captured'),
        )

    @staticmethod
    def results_header():
        d = AnalyzerCommon.common_results_header(algorithm_module.local_parameter_names)

        AnalyzerCommon.common_results(d)

        d['normal']             = lambda x: AnalyzerCommon._format_results(x, 'NormalSent')
        d['away']               = lambda x: AnalyzerCommon._format_results(x, 'AwaySent')
        d['choose']             = lambda x: AnalyzerCommon._format_results(x, 'ChooseSent')
        d['fake']               = lambda x: AnalyzerCommon._format_results(x, 'FakeSent')
        d['tfs']                = lambda x: AnalyzerCommon._format_results(x, 'TFS')
        d['pfs']                = lambda x: AnalyzerCommon._format_results(x, 'PFS')
        d['fake to normal']     = lambda x: AnalyzerCommon._format_results(x, 'FakeToNormal')
        d['fake nodes at end']  = lambda x: AnalyzerCommon._format_results(x, 'FakeNodesAtEnd')

        d['sent heatmap']       = lambda x: AnalyzerCommon._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: AnalyzerCommon._format_results(x, 'ReceivedHeatMap')

        d['fake nodes at end when captured']  = lambda x: AnalyzerCommon._format_results(x, 'filtered(FakeNodesAtEnd,Captured)')

        d['norm(sent,time taken)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(Sent,TimeTaken)')
        d['norm(norm(sent,time taken),network size)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(norm(Sent,TimeTaken),num_nodes)')
        d['norm(norm(sent,time taken),source rate)'] = lambda x: AnalyzerCommon._format_results(x, 'norm(norm(Sent,TimeTaken),source_rate)')
        d['norm(norm(norm(sent,time taken),network size),source rate)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(norm(norm(Sent,TimeTaken),num_nodes),source_rate)')

        d['norm(fake,time taken)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(FakeSent,TimeTaken)')
        d['norm(norm(fake,time taken),network size)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(norm(FakeSent,TimeTaken),num_nodes)')
        d['norm(norm(fake,time taken),source rate)'] = lambda x: AnalyzerCommon._format_results(x, 'norm(norm(FakeSent,TimeTaken),source_rate)')
        d['norm(norm(norm(fake,time taken),network size),source rate)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(norm(norm(FakeSent,TimeTaken),num_nodes),source_rate)')

        d['norm(normal,time taken)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(NormalSent,TimeTaken)')

        d['energy impact']      = lambda x: AnalyzerCommon._format_results(x, 'norm(energy_impact,1)')
        d['energy impact per node']   = lambda x: AnalyzerCommon._format_results(x, 'norm(energy_impact,num_nodes)')
        d['energy impact per node per second']   = lambda x: AnalyzerCommon._format_results(x, 'norm(norm(energy_impact,num_nodes),TimeTaken)')
        d['energy allowance used'] = lambda x: AnalyzerCommon._format_results(x, 'norm(daily_allowance_used,1)')

        return d
