from __future__ import print_function

import sys, re

from collections import Counter

from simulator.Simulator import OutputCatcher
from simulator.MetricsCommon import MetricsCommon

class Metrics(MetricsCommon):

    WHOLE_RE  = re.compile(r'DEBUG \((\d+)\): (.*)')
    FAKE_RE   = re.compile(r'The node has become a ([a-zA-Z]+)')

    def __init__(self, sim, configuration):
        super(Metrics, self).__init__(sim, configuration)

        self.COMMUNICATE = OutputCatcher(self.process_COMMUNICATE)
        self.COMMUNICATE.register(self.sim, 'Metric-COMMUNICATE')
        self.sim.add_output_processor(self.COMMUNICATE)

        self.FAKE_NOTIFICATION = OutputCatcher(self.process_FAKE_NOTIFICATION)
        self.FAKE_NOTIFICATION.register(self.sim, 'Fake-Notification')
        self.sim.add_output_processor(self.FAKE_NOTIFICATION)

        # Normal nodes becoming the source, or source nodes becoming normal
        self.SOURCE_CHANGE = OutputCatcher(self.process_SOURCE_CHANGE)
        self.SOURCE_CHANGE.register(self.sim, 'Metric-SOURCE_CHANGE')
        self.sim.add_output_processor(self.SOURCE_CHANGE)

        # Non-source nodes detecting the source has changed
        self.SOURCE_CHANGE_DETECT = OutputCatcher(self.process_SOURCE_CHANGE_DETECT)
        self.SOURCE_CHANGE_DETECT.register(self.sim, 'Metric-SOURCE_CHANGE_DETECT')
        self.sim.add_output_processor(self.SOURCE_CHANGE_DETECT)

        self.tfs_created = 0
        self.pfs_created = 0
        self.fake_to_normal = 0

        self.source_change_detected = {}

    def process_RCV(self, line):
        (kind, time, node_id, neighbour_source_id, ultimate_source_id, sequence_number, hop_count) = line.split(',')

        time = float(time) / self.sim.tossim.ticksPerSecond()
        node_id = int(node_id)
        neighbour_source_id = int(neighbour_source_id)
        ultimate_source_id = int(ultimate_source_id)
        sequence_number = int(sequence_number)
        hop_count = int(hop_count)

        if kind not in self.received:
            self.received[kind] = Counter()

        self.received[kind][node_id] += 1

        if node_id in self.sink_ids and kind == "Normal":
            self.normal_latency[sequence_number] = time - self.normal_sent_time[sequence_number]
            self.normal_hop_count.append(hop_count)

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

        time = float(time) / self.sim.tossim.ticksPerSecond()
        node_id = int(node_id)
        previous_source_id = int(previous_source_id)
        current_source_id = int(current_source_id)

        # TODO: proper metrics for this information
        # Ideas:
        # - Delay between a source change and a node detecting it

        self.source_change_detected.setdefault((previous_source_id, current_source_id), {})[node_id] = time

    def number_of_nodes_detected_change(self):
        return { k: len(times) for (k, times) in sorted(self.source_change_detected.items()) }

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

    @staticmethod
    def print_header(stream=sys.stdout):
        print("#" + "|".join(Metrics.items().keys()), file=stream)

    def print_results(self, stream=sys.stdout):
        results = [str(f(self)) for f in Metrics.items().values()]
        
        print("|".join(results), file=stream)
