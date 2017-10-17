from __future__ import division

from data.analysis import AnalyzerCommon

#from data.analysis import Analyse

#from simulator import SourcePeriodModel

"""class AnalyseWithOutlierDetection(Analyse):
    def detect_outlier(self, values):
        return None

        # Disable outlier detection, as we handle failing to capture
        # the source differently now
        # Discard simulations that didn't capture the source
        captured_index = self.headings.index("Captured")
        captured = bool(values[captured_index])

        if not captured:
            raise RuntimeError("Detected outlier, the source was not captured")

        # Discard simulations that took too long
        time_index = self.headings.index("TimeTaken")
        time_taken = float(values[time_index])

        network_size = int(self.opts['network_size'])
        source_period = float(SourcePeriodModel.eval_input(self.opts['source_period']))

        upper_bound = (network_size ** 2) * source_period

        # This can be much stricter than the protectionless upper bound on time.
        # As it can be changed once the simulations have been run.
        if time_taken >= upper_bound:
            raise RuntimeError("Detected outlier, the time taken is {}, upper bound is {}".format(
                time_taken, upper_bound))"""

algorithm_module = __import__(__package__, globals(), locals(), ['object'], -1)

class Analyzer(AnalyzerCommon):
    def __init__(self, results_directory):
        super(Analyzer, self).__init__(results_directory, self.results_header(), self.normalised_parameters())

    @staticmethod
    def normalised_parameters():
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

    @staticmethod
    def results_header():
        d = AnalyzerCommon.common_results_header(algorithm_module.local_parameter_names)

        AnalyzerCommon.common_results(d)

        d['normal']             = lambda x: AnalyzerCommon._format_results(x, 'NormalSent')

        d['node was source']    = lambda x: AnalyzerCommon._format_results(x, 'NodeWasSource', allow_missing=True)
        
        d['sent heatmap']       = lambda x: AnalyzerCommon._format_results(x, 'SentHeatMap')
        d['received heatmap']   = lambda x: AnalyzerCommon._format_results(x, 'ReceivedHeatMap')

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

        d['norm(sent,time taken)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(Sent,TimeTaken)')
        d['norm(norm(sent,time taken),network size)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(norm(Sent,TimeTaken),num_nodes)')
        d['norm(norm(sent,time taken),source rate)'] = lambda x: AnalyzerCommon._format_results(x, 'norm(norm(Sent,TimeTaken),source_rate)')
        d['norm(norm(norm(sent,time taken),network size),source rate)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(norm(norm(Sent,TimeTaken),num_nodes),source_rate)')

        d['norm(normal,time taken)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(NormalSent,TimeTaken)')
        d['norm(time taken,source period)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(TimeTaken,source_period)')

        d['energy impact']      = lambda x: AnalyzerCommon._format_results(x, 'norm(energy_impact,1)')
        d['energy impact per node']   = lambda x: AnalyzerCommon._format_results(x, 'norm(energy_impact,num_nodes)')
        d['energy impact per node per second']   = lambda x: AnalyzerCommon._format_results(x, 'norm(norm(energy_impact,num_nodes),TimeTaken)')
        d['energy allowance used'] = lambda x: AnalyzerCommon._format_results(x, 'norm(daily_allowance_used,1)')

        #d['good move ratio'] = lambda x: AnalyzerCommon._format_results(x, 'norm(good_move_ratio,1)')

        return d

    #def analyse_path(self, path):
    #    return AnalyseWithOutlierDetection(path)
