from __future__ import print_function, division

from simulator.MetricsCommon import MetricsCommon

ERROR_RTX_FAILED = 1001
ERROR_RTX_FAILED_TRYING_OTHER = 1002

class Metrics(MetricsCommon):
    def __init__(self, *args, **kwargs):
        super(Metrics, self).__init__(*args, **kwargs)

    @staticmethod
    def items():
        d = MetricsCommon.items()

        d["AwaySent"]               = lambda x: x.number_sent("Away")
        d["BeaconSent"]             = lambda x: x.number_sent("Beacon")
        d["PollSent"]               = lambda x: x.number_sent("Poll")

        d["FailedRtx"]              = lambda x: x.errors[ERROR_RTX_FAILED] + x.errors[ERROR_RTX_FAILED_TRYING_OTHER]
        d["FailedAvoidSink"]        = lambda x: x.errors[ERROR_RTX_FAILED_TRYING_OTHER] / x.num_normal_sent_if_finished()

        return d
