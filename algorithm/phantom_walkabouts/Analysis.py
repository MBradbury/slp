from __future__ import division

from data.analysis import AnalyzerCommon

algorithm_module = __import__(__package__, globals(), locals(), ['object'], -1)

def utility_star(value, cutoff):
    if value >= cutoff:
        return 0.0
    else:
        return 1.0 - (value / cutoff)

def utility_deliv(value, cutoff):
    if value <= cutoff:
        return 0.0
    else:
        return (value - cutoff) / (100 - cutoff)

def utility_of(name):
    if name == "ReceiveRatio":
        return utility_deliv
    else:
        return utility_star

def utility(x, parameters):
    return sum(
        weight * utility_of(name)(x.average_of[name], cutoff)
        for (name, cutoff, weight)
        in parameters
    )

class Analyzer(AnalyzerCommon):
    def __init__(self, results_directory):
        super(Analyzer, self).__init__(results_directory, self.results_header(), self.normalised_parameters())

    @staticmethod
    def normalised_parameters():
        return [
            ('Sent', 'TimeTaken'),
            (('Sent', 'TimeTaken'), 'num_nodes'),
        ]

    @staticmethod
    def results_header():
        d = AnalyzerCommon.common_results_header(algorithm_module.local_parameter_names)

        AnalyzerCommon.common_results(d)

        d['normal']             = lambda x: AnalyzerCommon._format_results(x, 'NormalSent')
        d['away']               = lambda x: AnalyzerCommon._format_results(x, 'AwaySent')
        d['beacon']             = lambda x: AnalyzerCommon._format_results(x, 'BeaconSent')

        d['paths reached end']  = lambda x: AnalyzerCommon._format_results(x, 'PathsReachedEnd')
        d['source dropped']     = lambda x: AnalyzerCommon._format_results(x, 'SourceDropped')
        d['path dropped']       = lambda x: AnalyzerCommon._format_results(x, 'PathDropped', allow_missing=True)
        d['path dropped length']= lambda x: AnalyzerCommon._format_results(x, 'PathDroppedLength', allow_missing=True)

        d['sent heatmap']       = lambda x: AnalyzerCommon._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: AnalyzerCommon._format_results(x, 'ReceivedHeatMap')

        d['norm(sent,time taken)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(Sent,TimeTaken)')
        d['norm(norm(sent,time taken),network size)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(norm(Sent,TimeTaken),num_nodes)')

        d['utility equal']      = lambda x: str(utility(x, [("Captured",               0.1,  0.25),        # Ranges from [0, 1]
                                                            ("ReceiveRatio",           0.75, 0.25),        # Ranges from [0, 1]
                                                            ("NormalLatency",          1,    0.25),        # Scale is in seconds
                                                            ("norm(Sent,TimeTaken)", 200,    0.25)]))

        d['utility animal']     = lambda x: str(utility(x, [("Captured",               0.1,  0.33),        # Ranges from [0, 1]
                                                            ("ReceiveRatio",           0.75, 0.33),        # Ranges from [0, 1]
                                                            ("NormalLatency",          1,    0),           # Scale is in seconds
                                                            ("norm(Sent,TimeTaken)", 200,    0.33)]))

        d['utility battle']     = lambda x: str(utility(x, [("Captured",               0.1,  0.25),        # Ranges from [0, 1]
                                                            ("ReceiveRatio",           0.75, 0.25),        # Ranges from [0, 1]
                                                            ("NormalLatency",          1,    0.4),         # Scale is in seconds
                                                            ("norm(Sent,TimeTaken)", 200,    0.1)]))

        return d
