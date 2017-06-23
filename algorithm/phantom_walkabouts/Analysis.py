from __future__ import division

from data.analysis import AnalyzerCommon
from data.analysis_extra.utility import Sigmoid, AnimalProtectionSigmoid, AssetMonitoringSigmoid, BattleSigmoid

algorithm_module = __import__(__package__, globals(), locals(), ['object'], -1)


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

		d['normalised captured']	= lambda x: str(x.average_of['Captured']/x.average_of['ReceiveRatio'])
		d['normalised norm(sent,time taken)']	= lambda x: str(x.average_of['norm(Sent,TimeTaken)']/x.average_of['ReceiveRatio'])

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

		d['utility animal']     = lambda x: str(Sigmoid.utility(x, [("Captured",    AnimalProtectionSigmoid.cr),   
															("ReceiveRatio",         AnimalProtectionSigmoid.dr),   
															("NormalLatency",        AnimalProtectionSigmoid.lat),  
															("norm(Sent,TimeTaken)", AnimalProtectionSigmoid.msg),
												]))

		d['utility monitor']     = lambda x: str(Sigmoid.utility(x, [("Captured",    AssetMonitoringSigmoid.cr),   
															("ReceiveRatio",         AssetMonitoringSigmoid.dr),   
															("NormalLatency",        AssetMonitoringSigmoid.lat),  
															("norm(Sent,TimeTaken)", AssetMonitoringSigmoid.msg),
												]))

		d['utility military']   = lambda x: str(Sigmoid.utility(x, [("Captured",  BattleSigmoid.cr),
															("ReceiveRatio",        BattleSigmoid.dr),   
															("NormalLatency",       BattleSigmoid.lat),
															("norm(Sent,TimeTaken)",    BattleSigmoid.msg),
												]))

		return d
