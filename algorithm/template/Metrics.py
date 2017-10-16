
from simulator.MetricsCommon import MetricsCommon, FakeMetricsCommon

class Metrics(FakeMetricsCommon):

    def __init__(self, *args, **kwargs):
        super(Metrics, self).__init__(*args, **kwargs)

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["ChooseSent"]             = lambda x: x.number_sent("Choose")
        d["AwaySent"]               = lambda x: x.number_sent("Away")

        d.update(FakeMetricsCommon.items({"TFS": "TempFakeNode", "PFS": "PermFakeNode"}))

        return d
