
from data.analysis import AnalyzerCommon

algorithm_module = __import__(__package__, globals(), locals(), ['object'])

class Analyzer(AnalyzerCommon):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def normalised_parameters(self):
        return (
            ('Sent', 'TimeTaken'),
            (('Sent', 'TimeTaken'), 'num_nodes'),
            ((('Sent', 'TimeTaken'), 'num_nodes'), 'source_rate'),
            ('FakeSent', 'TimeTaken'),
            (('FakeSent', 'TimeTaken'), 'source_rate'),
            ('NormalSent', 'TimeTaken'),

            ('energy_impact', 'num_nodes'),
            (('energy_impact', 'num_nodes'), 'TimeTaken'),
            ('daily_allowance_used', '1'),
        )

    def results_header(self):
        d = self.common_results_header(algorithm_module.local_parameter_names)

        self.common_results(d)
        
        d['normal']             = lambda x: self._format_results(x, 'NormalSent')
        d['away']               = lambda x: self._format_results(x, 'AwaySent')
        d['choose']             = lambda x: self._format_results(x, 'ChooseSent')
        d['fake']               = lambda x: self._format_results(x, 'FakeSent')
        d['beacon']             = lambda x: self._format_results(x, 'BeaconSent')
        d['tfs']                = lambda x: self._format_results(x, 'TFS')
        d['pfs']                = lambda x: self._format_results(x, 'PFS')
        d['tailfs']             = lambda x: self._format_results(x, 'TailFS')
        d['fake to normal']     = lambda x: self._format_results(x, 'FakeToNormal')
        d['fake to fake']       = lambda x: self._format_results(x, 'FakeToFake')

        d['parent changes']     = lambda x: self._format_results(x, 'TotalParentChanges')
        d['true parent changes']= lambda x: self._format_results(x, 'TotalTrueParentChanges')
        
        d['sent heatmap']       = lambda x: self._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: self._format_results(x, 'ReceivedHeatMap')
        d['parent change heatmap']= lambda x: self._format_results(x, 'ParentChangeHeatMap')

        d['norm(sent,time taken)']   = lambda x: self._format_results(x, 'norm(Sent,TimeTaken)')
        d['norm(norm(sent,time taken),network size)']   = lambda x: self._format_results(x, 'norm(norm(Sent,TimeTaken),num_nodes)')
        d['norm(norm(norm(sent,time taken),network size),source rate)']   = lambda x: self._format_results(x, 'norm(norm(norm(Sent,TimeTaken),num_nodes),source_rate)')

        d['norm(fake,time taken)']   = lambda x: self._format_results(x, 'norm(FakeSent,TimeTaken)')
        d['norm(norm(fake,time taken),source rate)'] = lambda x: self._format_results(x, 'norm(norm(FakeSent,TimeTaken),source_rate)')

        d['norm(normal,time taken)']   = lambda x: self._format_results(x, 'norm(NormalSent,TimeTaken)')

        d['energy impact per node']   = lambda x: self._format_results(x, 'norm(energy_impact,num_nodes)')
        d['energy impact per node per second']   = lambda x: self._format_results(x, 'norm(norm(energy_impact,num_nodes),TimeTaken)')
        d['energy allowance used'] = lambda x: self._format_results(x, 'norm(daily_allowance_used,1)')

        return d
