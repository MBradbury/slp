
from data.analysis import AnalyzerCommon

class Analyzer(AnalyzerCommon):
    def __init__(self, results_directory):
        super(Analyzer, self).__init__(results_directory, self.results_header(), self.normalised_parameters())

    @staticmethod
    def normalised_parameters():
        return (
            ('Sent', 'TimeTaken'),
            ('FakeSent', 'TimeTaken'),
            (('FakeSent', 'TimeTaken'), 'source_rate'),
            ('NormalSent', 'TimeTaken'),

            ('energy_impact', 'network_size'),
            (('energy_impact', 'network_size'), 'TimeTaken'),
            ('daily_allowance_used', '1'),
        )

    @staticmethod
    def results_header():
        d = AnalyzerCommon.common_results_header()

        d['approach']           = lambda x: x.opts['approach']

        AnalyzerCommon.common_results(d)
        
        d['captured']           = lambda x: str(x.average_of['Captured'])
        d['attacker moves']     = lambda x: AnalyzerCommon._format_results(x, 'AttackerMoves')
        d['attacker distance']  = lambda x: AnalyzerCommon._format_results(x, 'AttackerDistance', average_corrector=Analyzer._correct_attacker_distance)
        d['received ratio']     = lambda x: AnalyzerCommon._format_results(x, 'ReceiveRatio')
        d['normal latency']     = lambda x: AnalyzerCommon._format_results(x, 'NormalLatency')
        d['normal']             = lambda x: AnalyzerCommon._format_results(x, 'NormalSent')
        d['away']               = lambda x: AnalyzerCommon._format_results(x, 'AwaySent')
        d['choose']             = lambda x: AnalyzerCommon._format_results(x, 'ChooseSent')
        d['fake']               = lambda x: AnalyzerCommon._format_results(x, 'FakeSent')
        d['tfs']                = lambda x: AnalyzerCommon._format_results(x, 'TFS')
        d['pfs']                = lambda x: AnalyzerCommon._format_results(x, 'PFS')
        d['fake to normal']     = lambda x: AnalyzerCommon._format_results(x, 'FakeToNormal')
        d['ssd']                = lambda x: AnalyzerCommon._format_results(x, 'NormalSinkSourceHops')
        
        d['sent heatmap']       = lambda x: AnalyzerCommon._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: AnalyzerCommon._format_results(x, 'ReceivedHeatMap')

        d['norm(sent,time taken)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(Sent,TimeTaken)')
       
        d['norm(fake,time taken)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(FakeSent,TimeTaken)')
        d['norm(norm(fake,time taken),source rate)'] = lambda x: AnalyzerCommon._format_results(x, 'norm(norm(FakeSent,TimeTaken),source_rate)')

        d['norm(normal,time taken)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(NormalSent,TimeTaken)')

        d['energy impact per node']   = lambda x: AnalyzerCommon._format_results(x, 'norm(energy_impact,network_size)')
        d['energy impact per node per second']   = lambda x: AnalyzerCommon._format_results(x, 'norm(norm(energy_impact,network_size),TimeTaken)')
        d['energy allowance used'] = lambda x: AnalyzerCommon._format_results(x, 'norm(daily_allowance_used,1)')

        return d

    @staticmethod
    def _correct_attacker_distance(x):
        """The format was changed to have a pair as the key,
        this allows for multiple attackers and multiple sources."""
        if isinstance(x, dict) and 0 in x:
            return {(0, 0): x[0]}
        else:
            return x
