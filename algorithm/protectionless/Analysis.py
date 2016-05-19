from __future__ import division

from data.analysis import Analyse, AnalysisResults, AnalyzerCommon

from simulator import SourcePeriodModel

class AnalyseWithOutlierDetection(Analyse):
    def detect_outlier(self, values):
        return None

        # Disable outlier detection, as we handle failing to capture
        # the source differently now
        """# Discard simulations that didn't capture the source
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

class Analyzer(AnalyzerCommon):
    def __init__(self, results_directory):
        super(Analyzer, self).__init__(results_directory, self.results_header(), self.normalised_parameters())

    @staticmethod
    def normalised_parameters():
        return (
            ('Sent', 'TimeTaken'),
            ('NormalSent', 'TimeTaken'),
            ('TimeTaken', 'source_period'),

            ('energy_impact', 'network_size'),
            (('energy_impact', 'network_size'), 'TimeTaken'),
        )

    @staticmethod
    def results_header():
        d = AnalyzerCommon.common_results_header()

        d['sent']               = lambda x: AnalyzerCommon._format_results(x, 'Sent')
        d['received']           = lambda x: AnalyzerCommon._format_results(x, 'Received')
        d['captured']           = lambda x: str(x.average_of['Captured'])
        d['attacker moves']     = lambda x: AnalyzerCommon._format_results(x, 'AttackerMoves')
        d['attacker distance']  = lambda x: AnalyzerCommon._format_results(x, 'AttackerDistance', average_corrector=Analyzer._correct_attacker_distance)
        d['received ratio']     = lambda x: AnalyzerCommon._format_results(x, 'ReceiveRatio')
        d['normal latency']     = lambda x: AnalyzerCommon._format_results(x, 'NormalLatency')
        d['time taken']         = lambda x: AnalyzerCommon._format_results(x, 'TimeTaken')
        d['time taken median']  = lambda x: str(x.median_of['TimeTaken'])
        d['safety period']      = lambda x: str(x.average_of['TimeTaken'] * 2.0)
        d['normal']             = lambda x: AnalyzerCommon._format_results(x, 'NormalSent')
        d['ssd']                = lambda x: AnalyzerCommon._format_results(x, 'NormalSinkSourceHops')

        d['node was source']    = lambda x: AnalyzerCommon._format_results(x, 'NodeWasSource', allow_missing=True)

        d['wall time']          = lambda x: AnalyzerCommon._format_results(x, 'WallTime', allow_missing=True)
        d['event count']        = lambda x: AnalyzerCommon._format_results(x, 'EventCount', allow_missing=True)
        
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
        d['norm(normal,time taken)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(NormalSent,TimeTaken)')
        d['norm(time taken,source period)']   = lambda x: AnalyzerCommon._format_results(x, 'norm(TimeTaken,source_period)')

        d['energy impact per node']   = lambda x: AnalyzerCommon._format_results(x, 'norm(energy_impact,network_size)')
        d['energy impact per node per second']   = lambda x: AnalyzerCommon._format_results(x, 'norm(norm(energy_impact,network_size),TimeTaken)')
        d['energy impact time'] = lambda x: AnalyzerCommon._format_results(x, 'energy_impact_time')

        return d

    #def analyse_path(self, path):
    #    return AnalyseWithOutlierDetection(path)

    @staticmethod
    def _correct_attacker_distance(x):
        if isinstance(x, dict) and 0 in x:
            return {(0, 0): x[0]}
        else:
            return x
