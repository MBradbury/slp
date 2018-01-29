
from data.analysis import AnalyzerCommon

algorithm_module = __import__(__package__, globals(), locals(), ['object'])

class Analyzer(AnalyzerCommon):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def normalised_parameters(self):
        return (
            ('Sent', 'TimeTaken'),
            ('NormalSent', 'TimeTaken'),

            #('energy_impact', 'num_nodes'),
            #(('energy_impact', 'num_nodes'), 'TimeTaken'),
            #('daily_allowance_used', '1'),
        )

    def filtered_parameters(self):
        return (
            ('FailedAvoidSink', 'Captured'),
        )

    def results_header(self):
        d = self.common_results_header(algorithm_module.local_parameter_names)

        self.common_results(d)

        d['normal']             = lambda x: self._format_results(x, 'NormalSent')
        d['away']               = lambda x: self._format_results(x, 'AwaySent')
        d['beacon']             = lambda x: self._format_results(x, 'BeaconSent')
        d['poll']               = lambda x: self._format_results(x, 'PollSent')

        d['failed rtx']         = lambda x: self._format_results(x, 'FailedRtx')
        d['failed avoid sink']  = lambda x: self._format_results(x, 'FailedAvoidSink')

        d['failed avoid sink when captured']  = lambda x: self._format_results(x, 'filtered(FailedAvoidSink,Captured)')

        #d['node was source']    = lambda x: self._format_results(x, 'NodeWasSource')

        d['sent heatmap']       = lambda x: self._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: self._format_results(x, 'ReceivedHeatMap')

        d['norm(sent,time taken)']   = lambda x: self._format_results(x, 'norm(Sent,TimeTaken)')
        d['norm(normal,time taken)']   = lambda x: self._format_results(x, 'norm(NormalSent,TimeTaken)')

        #d['energy impact per node']   = lambda x: self._format_results(x, 'norm(energy_impact,num_nodes)')
        #d['energy impact per node per second']   = lambda x: self._format_results(x, 'norm(norm(energy_impact,num_nodes),TimeTaken)')
        #d['energy allowance used'] = lambda x: self._format_results(x, 'norm(daily_allowance_used,1)')

        return d
