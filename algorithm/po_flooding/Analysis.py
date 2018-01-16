from __future__ import division

from data.analysis import Analyse, AnalyzerCommon

algorithm_module = __import__(__package__, globals(), locals(), ['object'])

class Analyzer(AnalyzerCommon):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def normalised_parameters(self):
        return (
            ('Sent', 'TimeTaken'),
            (('Sent', 'TimeTaken'), 'num_nodes'),
            (('Sent', 'TimeTaken'), 'source_rate'),
            ((('Sent', 'TimeTaken'), 'num_nodes'), 'source_rate'),

            ('NormalSent', 'TimeTaken'),

            ('TimeTaken', 'source_period'),

            #('energy_impact', '1'),
            #('energy_impact', 'num_nodes'),
            #(('energy_impact', 'num_nodes'), 'TimeTaken'),
            #('daily_allowance_used', '1'),
            
            #('good_move_ratio', '1'),
        )

    def results_header(self):
        d = self.common_results_header(algorithm_module.local_parameter_names)

        self.common_results(d)

        d['normal']             = lambda x: self._format_results(x, 'NormalSent')

        d['node was source']    = lambda x: self._format_results(x, 'NodeWasSource', allow_missing=True)
        
        d['sent heatmap']       = lambda x: self._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: self._format_results(x, 'ReceivedHeatMap')

        def dp(x, n1, n2):

            d1 = x.average_of.get(n1, None)
            d2 = x.average_of.get(n2, None)

            # Allow missing results
            if d1 is None or d2 is None:
                return "None"

            result = {}

            for (key, value) in d1.items():
                result[key] = value / (d1[key] + d2[key])

            return str(result)

        d['rcvd further hops']     = lambda x: dp(x, 'ReceivedFromFurtherHops', 'ReceivedFromCloserOrSameHops')
        d['rcvd further meters']   = lambda x: dp(x, 'ReceivedFromFurtherMeters', 'ReceivedFromCloserOrSameMeters')

        d['norm(sent,time taken)']   = lambda x: self._format_results(x, 'norm(Sent,TimeTaken)')
        d['norm(norm(sent,time taken),network size)']   = lambda x: self._format_results(x, 'norm(norm(Sent,TimeTaken),num_nodes)')
        d['norm(norm(sent,time taken),source rate)'] = lambda x: self._format_results(x, 'norm(norm(Sent,TimeTaken),source_rate)')
        d['norm(norm(norm(sent,time taken),network size),source rate)']   = lambda x: self._format_results(x, 'norm(norm(norm(Sent,TimeTaken),num_nodes),source_rate)')

        d['norm(normal,time taken)']   = lambda x: self._format_results(x, 'norm(NormalSent,TimeTaken)')
        d['norm(time taken,source period)']   = lambda x: self._format_results(x, 'norm(TimeTaken,source_period)')

        #d['energy impact']      = lambda x: self._format_results(x, 'norm(energy_impact,1)')
        #d['energy impact per node']   = lambda x: self._format_results(x, 'norm(energy_impact,num_nodes)')
        #d['energy impact per node per second']   = lambda x: self._format_results(x, 'norm(norm(energy_impact,num_nodes),TimeTaken)')
        #d['energy allowance used'] = lambda x: self._format_results(x, 'norm(daily_allowance_used,1)')

        #d['good move ratio'] = lambda x: self._format_results(x, 'norm(good_move_ratio,1)')

        return d
