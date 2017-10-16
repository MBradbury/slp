from __future__ import print_function, division

from simulator.MetricsCommon import MetricsCommon, FakeMetricsCommon, TreeMetricsCommon

class Metrics(FakeMetricsCommon, TreeMetricsCommon):
    def __init__(self, *args, **kwargs):
        super(Metrics, self).__init__(*args, **kwargs)

    @staticmethod
    def items():
        d = MetricsCommon.items()

        d["ChooseSent"]             = lambda x: x.number_sent("Choose")
        d["AwaySent"]               = lambda x: x.number_sent("Away")
        d["BeaconSent"]             = lambda x: x.number_sent("Beacon")
        d["InformSent"]             = lambda x: x.number_sent("Inform")
        d["CTPBeaconSent"]          = lambda x: x.number_sent("CTPBeacon")

        d.update(FakeMetricsCommon.items({"TFS": "TempFakeNode", "PFS": "PermFakeNode", "TailFS": "TailFakeNode"}))
        d.update(TreeMetricsCommon.items())

        return d
