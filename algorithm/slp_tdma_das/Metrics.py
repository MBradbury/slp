
from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):
    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

    def first_normal_send_times(self):
        result = {}

        for ((top_node_id, seq_no), time) in self.normal_sent_time.items():
            if top_node_id not in result:
                result[top_node_id] = time
            else:
                result[top_node_id] = min(result[top_node_id], time)

        return result

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["DissemSent"]               = lambda x: x.number_sent("Dissem")
        d["ChangeSent"]               = lambda x: x.number_sent("Change")
        d["SearchSent"]               = lambda x: x.number_sent("Search")
        d["EmptyNormalSent"]          = lambda x: x.number_sent("EmptyNormal")

        d["FirstSendTime"]            = lambda x: x.first_normal_send_times()

        return d
