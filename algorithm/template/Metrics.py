
import re

from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):

    FAKE_RE = re.compile(r'The node has become a ([a-zA-Z]+)')

    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

        self.register('Fake-Notification', self.process_FAKE_NOTIFICATION)

        self.tfs_created = 0
        self.pfs_created = 0
        self.fake_to_normal = 0

    def process_FAKE_NOTIFICATION(self, d_or_e, node_id, time, detail):
        match = self.FAKE_RE.match(detail)
        if match is not None:
            kind = match.group(1)
            
            if kind == "TFS":
                self.tfs_created += 1
            elif kind == "PFS":
                self.pfs_created += 1
            elif kind == "Normal":
                self.fake_to_normal += 1
            else:
                raise RuntimeError("Unknown kind {}".format(kind))

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["FakeSent"]               = lambda x: x.number_sent("Fake")
        d["ChooseSent"]             = lambda x: x.number_sent("Choose")
        d["AwaySent"]               = lambda x: x.number_sent("Away")
        d["TFS"]                    = lambda x: x.tfs_created
        d["PFS"]                    = lambda x: x.pfs_created
        d["FakeToNormal"]           = lambda x: x.fake_to_normal

        return d
