
from simulator.MetricsCommon import MetricsCommon, FakeMetricsCommon, DutyCycleMetricsCommon

class Metrics(FakeMetricsCommon, DutyCycleMetricsCommon):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_message_format("Fake", "!IHhBBII", ("seq", "src", "sdst", "type", "scnt", "sdur", "sper"))

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["ChooseSent"]             = lambda x: x.number_sent("Choose")
        d["AwaySent"]               = lambda x: x.number_sent("Away")
        d["BeaconSent"]             = lambda x: x.number_sent("Beacon")
        d["NotifySent"]             = lambda x: x.number_sent("Notify")

        d.update(FakeMetricsCommon.items({"TFS": "TempFakeNode", "PFS": "PermFakeNode", "TailFS": "TailFakeNode"}))
        d.update(DutyCycleMetricsCommon.items())

        return d
