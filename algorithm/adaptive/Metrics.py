
from simulator.MetricsCommon import MetricsCommon, FakeMetricsCommon, DutyCycleMetricsCommon

class Metrics(FakeMetricsCommon, DutyCycleMetricsCommon):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["ChooseSent"]             = lambda x: x.number_sent("Choose")
        d["AwaySent"]               = lambda x: x.number_sent("Away")
        d["NotifySent"]             = lambda x: x.number_sent("Notify")

        d.update(FakeMetricsCommon.items({"TFS": "TempFakeNode", "PFS": "PermFakeNode"}))
        d.update(DutyCycleMetricsCommon.items())

        return d
