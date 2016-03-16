
import re

from simulator.Simulation import OutputCatcher
from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):

    WHOLE_RE  = re.compile(r'DEBUG \((\d+)\): (.*)')
    FAKE_RE   = re.compile(r'The node has become a ([a-zA-Z]+)')

    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

        self.register('Fake-Notification', self.process_FAKE_NOTIFICATION)

        # Non-source nodes detecting the source has changed
        self.register('Metric-SOURCE_CHANGE_DETECT', self.process_SOURCE_CHANGE_DETECT)

        self.tfs_created = 0
        self.pfs_created = 0
        self.fake_to_normal = 0

        self.source_change_detected = {}

    def process_FAKE_NOTIFICATION(self, line):
        match = self.WHOLE_RE.match(line)
        if match is None:
            return None

        node_id = int(match.group(1))
        detail = match.group(2)

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

    def process_SOURCE_CHANGE_DETECT(self, line):
        (time, node_id, previous_source_id, current_source_id) = line.split(',')

        time = self.sim.ticks_to_seconds(time)
        node_id = int(node_id)
        previous_source_id = int(previous_source_id)
        current_source_id = int(current_source_id)

        # TODO: proper metrics for this information
        # Ideas:
        # - Delay between a source change and a node detecting it

        self.source_change_detected.setdefault((previous_source_id, current_source_id), {})[node_id] = time

    def number_of_nodes_detected_change(self):
        return {k: len(times) for (k, times) in sorted(self.source_change_detected.items())}

    @staticmethod
    def items():
        d = MetricsCommon.items()
        d["FakeSent"]               = lambda x: x.number_sent("Fake")
        d["ChooseSent"]             = lambda x: x.number_sent("Choose")
        d["AwaySent"]               = lambda x: x.number_sent("Away")
        d["TFS"]                    = lambda x: x.tfs_created
        d["PFS"]                    = lambda x: x.pfs_created
        d["FakeToNormal"]           = lambda x: x.fake_to_normal
        d["SourceChangeDetected"]   = lambda x: x.source_change_detected
        d["NodesDetectedSrcChange"] = lambda x: x.number_of_nodes_detected_change()

        return d
