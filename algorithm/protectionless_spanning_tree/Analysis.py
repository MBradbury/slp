
from data.analysis import AnalyzerCommon

algorithm_module = __import__(__package__, globals(), locals(), ['object'])

class Analyzer(AnalyzerCommon):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def normalised_parameters(self):
        return (
            ('Sent', 'TimeTaken'),
            ('NormalSent', 'TimeTaken'),
            ('TimeTaken', 'source_period')
        )

    def results_header(self):
        d = self.common_results_header(algorithm_module.local_parameter_names)

        self.common_results(d)

        d['normal']             = lambda x: self._format_results(x, 'NormalSent')

        d['node was source']    = lambda x: self._format_results(x, 'NodeWasSource')

        d['sent heatmap']       = lambda x: self._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: self._format_results(x, 'ReceivedHeatMap')

        d['norm(sent,time taken)']   = lambda x: self._format_results(x, 'norm(Sent,TimeTaken)')
        d['norm(normal,time taken)']   = lambda x: self._format_results(x, 'norm(NormalSent,TimeTaken)')
        d['norm(time taken,source period)']   = lambda x: self._format_results(x, 'norm(TimeTaken,source_period)')

        return d
