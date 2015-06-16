
from collections import OrderedDict

from data.analysis import AnalyzerCommon

class Analyzer(AnalyzerCommon):
    def __init__(self, results_directory):
        d = OrderedDict()
        self._set_results_header(d)
        d['fake period']        = lambda x: x.opts['fake_period']
        d['temp fake duration'] = lambda x: x.opts['temp_fake_duration']
        d['pr(tfs)']            = lambda x: x.opts['pr_tfs']
        d['pr(pfs)']            = lambda x: x.opts['pr_pfs']
        
        d['sent']               = lambda x: self._format_results(x, 'Sent')
        d['received']           = lambda x: self._format_results(x, 'Received')
        d['captured']           = lambda x: str(x.average_of['Captured'])
        d['attacker moves']     = lambda x: self._format_results(x, 'AttackerMoves')
        d['attacker distance']  = lambda x: self._format_results(x, 'AttackerDistance')
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
        
        d['sent heatmap']       = lambda x: self._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: self._format_results(x, 'ReceivedHeatMap')

        super(Analyzer, self).__init__(results_directory, d)
