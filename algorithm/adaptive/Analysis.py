
from collections import OrderedDict

from data.analysis import AnalyzerCommon

class Analyzer(AnalyzerCommon):
    def __init__(self, results_directory):
        d = OrderedDict()
        self._set_results_header(d)
        d['approach']           = lambda x: x.opts['approach']
        
        d['sent']               = lambda x: self._format_results(x, 'Sent')
        d['received']           = lambda x: self._format_results(x, 'Received')
        d['captured']           = lambda x: str(x.average_of['Captured'])
        d['attacker moves']     = lambda x: self._format_results(x, 'AttackerMoves')
        d['attacker distance']  = lambda x: self._format_results(x, 'AttackerDistance', average_corrector=Analyzer._correct_attacker_distance)
        d['received ratio']     = lambda x: self._format_results(x, 'ReceiveRatio')
        d['normal latency']     = lambda x: self._format_results(x, 'NormalLatency')
        d['time taken']         = lambda x: self._format_results(x, 'TimeTaken')
        d['normal']             = lambda x: self._format_results(x, 'NormalSent')
        d['away']               = lambda x: self._format_results(x, 'AwaySent')
        d['choose']             = lambda x: self._format_results(x, 'ChooseSent')
        d['fake']               = lambda x: self._format_results(x, 'FakeSent')
        d['tfs']                = lambda x: self._format_results(x, 'TFS')
        d['pfs']                = lambda x: self._format_results(x, 'PFS')
        d['fake to normal']     = lambda x: self._format_results(x, 'FakeToNormal')
        d['ssd']                = lambda x: self._format_results(x, 'NormalSinkSourceHops')

        d['wall time']          = lambda x: self._format_results(x, 'WallTime')
        d['event count']        = lambda x: self._format_results(x, 'EventCount')
        
        d['sent heatmap']       = lambda x: self._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: self._format_results(x, 'ReceivedHeatMap')

        d['norm(sent,time taken)']   = lambda x: self._format_results(x, 'norm(Sent,TimeTaken)')
       
        d['norm(fake,time taken)']   = lambda x: self._format_results(x, 'norm(FakeSent,TimeTaken)')
        d['norm(norm(fake,time taken),source rate)'] = lambda x: self._format_results(x, 'norm(norm(FakeSent,TimeTaken),source_rate)')

        normalised = [
            ('Sent', 'TimeTaken'),
            ('FakeSent', 'TimeTaken'),
            (('FakeSent', 'TimeTaken'), 'source_rate'),
        ]

        super(Analyzer, self).__init__(results_directory, d, normalised)

    @staticmethod
    def _correct_attacker_distance(x):
        if isinstance(x, dict) and 0 in x:
            return {(0, 0): x[0]}
        else:
            return x
