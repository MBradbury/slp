
from simulator.Simulation import OutputCatcher
from simulator.MetricsCommon import MetricsCommon

from collections import Counter

class Metrics(MetricsCommon):
    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

        self.register('Metric-Pool-Full', self.process_POOL_FULL)

        self.pool_full = Counter()

    def process_POOL_FULL(self, line):
    	(node_id,) = line.split(",")

    	node_id = int(node_id)

    	self.pool_full[node_id] += 1

    def first_normal_send_times(self):
    	result = {}

    	for ((node_id, seq_no), time) in self.normal_sent_time.items():
    		if node_id not in result:
    			result[node_id] = time
    		else:
    			result[node_id] = min(result[node_id], time)

    	return result

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["DissemSent"]               = lambda x: x.number_sent("Dissem")
        d["ChangeSent"]               = lambda x: x.number_sent("Change")
        d["SearchSent"]               = lambda x: x.number_sent("Search")

        d["PoolFull"]                 = lambda x: dict(x.pool_full)
        d["FirstSendTime"]            = lambda x: x.first_normal_send_times()

        return d
