
from collections import OrderedDict

from data.analysis import AnalyzerCommon

class Analyzer(AnalyzerCommon):
    def __init__(self, results_directory):
        d = OrderedDict()
        d['network size']       = lambda x: x.opts['network_size']
        d['configuration']      = lambda x: x.opts['configuration']
        d['source period']      = lambda x: x.opts['source_period']
        d['attacker model']     = lambda x: x.opts['attacker_model']
        d['walk length']        = lambda x: x.opts['random_walk_hops']
        d['walk retries']       = lambda x: x.opts['random_walk_retries']

        def format_results(x, name):
            if name in x.variance_of:
                return "{}({})".format(x.average_of[name], x.variance_of[name])
            else:
                return "{}".format(x.average_of[name])
        
        d['sent']               = lambda x: format_results(x, 'Sent')
        d['received']           = lambda x: format_results(x, 'Received')
        d['captured']           = lambda x: str(x.average_of['Captured'])
        d['attacker moves']     = lambda x: format_results(x, 'AttackerMoves')
        d['attacker distance']  = lambda x: format_results(x, 'AttackerDistance')
        d['received ratio']     = lambda x: format_results(x, 'ReceiveRatio')
        d['normal latency']     = lambda x: format_results(x, 'NormalLatency')
        d['time taken']         = lambda x: format_results(x, 'TimeTaken')
        d['normal']             = lambda x: format_results(x, 'NormalSent')
        d['away']               = lambda x: format_results(x, 'AwaySent')
        d['beacon']             = lambda x: format_results(x, 'BeaconSent')
        d['ssd']                = lambda x: format_results(x, 'NormalSinkSourceHops')

        d['wall time']          = lambda x: format_results(x, 'WallTime')
        d['event count']        = lambda x: format_results(x, 'EventCount')
        
        d['sent heatmap']       = lambda x: format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: format_results(x, 'ReceivedHeatMap')

        super(Analyzer, self).__init__(results_directory, d)
