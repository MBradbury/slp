
from simulator.MetricsCommon import MetricsCommon, DutyCycleMetricsCommon

import numpy as np

ERROR_RTX_FAILED = 1001
ERROR_RTX_FAILED_TRYING_OTHER = 1002

METRIC_GENERIC_TIME_TAKEN_TO_SEND = 1

class Metrics(DutyCycleMetricsCommon):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._time_taken_to_send = {}

        self.register_generic(METRIC_GENERIC_TIME_TAKEN_TO_SEND, self._process_time_taken_to_send)

    def _process_time_taken_to_send(self, d_or_e, node_id, time, data):
        (ultimate_source_id, seqno, proximate_source_id, time_taken_to_send_ms) = data.split(",")

        ord_ultimate_source_id, top_ultimate_source_id = self._process_node_id(ultimate_source_id)
        ord_proximate_source_id, top_proximate_source_id = self._process_node_id(proximate_source_id)
        ord_node_id, top_node_id = self._process_node_id(node_id)

        message = (top_ultimate_source_id, int(seqno))
        key = (top_proximate_source_id, top_node_id)

        self._time_taken_to_send.setdefault(message, {})[key] = int(time_taken_to_send_ms)

    def average_time_taken_to_send(self):
        return {
            message: (round(np.mean(list(rest.values())), 1), round(np.std(list(rest.values())), 1))

            for (message, rest)
            in self._time_taken_to_send.items()
        }


    @staticmethod
    def items():
        d = MetricsCommon.items()

        d["AwaySent"]               = lambda x: x.number_sent("Away")
        d["BeaconSent"]             = lambda x: x.number_sent("Beacon")
        d["PollSent"]               = lambda x: x.number_sent("Poll")

        d["FailedRtx"]              = lambda x: x.errors[ERROR_RTX_FAILED] + x.errors[ERROR_RTX_FAILED_TRYING_OTHER]
        d["FailedAvoidSink"]        = lambda x: x.errors[ERROR_RTX_FAILED_TRYING_OTHER] / x.num_normal_sent_if_finished()

        d["TimeTakenToSend"]        = lambda x: MetricsCommon.compressed_dict_str(x.average_time_taken_to_send())

        d.update(DutyCycleMetricsCommon.items())

        return d
