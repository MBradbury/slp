
from data.analysis import AnalyzerCommon

algorithm_module = __import__(__package__, globals(), locals(), ['object'])

class Analyzer(AnalyzerCommon):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def normalised_parameters(self):
        return (
            ('Sent', 'TimeTaken'),
            (('Sent', 'TimeTaken'), 'num_nodes'),
        )

    def results_header(self):
        d = self.common_results_header(algorithm_module.local_parameter_names)

        self.common_results(d)

        d['normal']             = lambda x: self._format_results(x, 'NormalSent')
        d['empty normal']       = lambda x: self._format_results(x, 'EmptyNormalSent')
        d['dissem']             = lambda x: self._format_results(x, 'DissemSent')
        d['search']             = lambda x: self._format_results(x, 'SearchSent')
        d['change']             = lambda x: self._format_results(x, 'ChangeSent')
        d['crash']              = lambda x: self._format_results(x, 'CrashSent')

        d['node was source']    = lambda x: self._format_results(x, 'NodeWasSource', allow_missing=True)

        d['sent heatmap']       = lambda x: self._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: self._format_results(x, 'ReceivedHeatMap')

        d['norm(sent,time taken)'] = lambda x: self._format_results(x, 'norm(Sent,TimeTaken)')
        d['norm(norm(sent,time taken),network size)'] = lambda x: self._format_results(x, 'norm(norm(Sent,TimeTaken),num_nodes)')

        d['control sent']       = lambda x: str(x.describe_of['SearchSent']['mean'] + x.describe_of['ChangeSent']['mean'] + x.describe_of['CrashSent']['mean'])
        d['path sent']          = lambda x: str(x.describe_of['SearchSent']['mean'] + x.describe_of['ChangeSent']['mean'])
        d['overhead']           = lambda x: str((x.describe_of['SearchSent']['mean'] + x.describe_of['ChangeSent']['mean'] + x.describe_of['CrashSent']['mean'])/x.describe_of['NormalSent']['mean'])

        return d
