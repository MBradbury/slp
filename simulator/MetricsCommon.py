
from collections import Counter, OrderedDict
import itertools

from numpy import mean
from scipy.spatial.distance import euclidean

class MetricsCommon(object):
    def __init__(self, sim, configuration):
        self.sim = sim
        self.configuration = configuration

        self.source_ids = set([ configuration.source_id ])
        self.sink_ids = set([ configuration.sink_id ])

        self.sent = {}
        self.received = {}

        self.normal_sent_time = {}
        self.normal_latency = {}
        self.normal_hop_count = []

        self.wall_time = 0
        self.event_count = 0

        self.became_source_times = {}
        self.became_normal_after_source_times = {}

    def process_BCAST(self, line):
        (kind, time, node_id, status, sequence_number) = line.split(',')

        if status == "success":
            time = float(time) / self.sim.tossim.ticksPerSecond()
            node_id = int(node_id)
            sequence_number = int(sequence_number)

            if kind not in self.sent:
                self.sent[kind] = Counter()

            self.sent[kind][node_id] += 1

            if node_id in self.source_ids and kind == "Normal":
                self.normal_sent_time[sequence_number] = time

    def process_RCV(self, line):
        (kind, time, node_id, source_id, sequence_number, hop_count) = line.split(',')

        time = float(time) / self.sim.tossim.ticksPerSecond()
        node_id = int(node_id)
        source_id = int(source_id)
        sequence_number = int(sequence_number)
        hop_count = int(hop_count)

        if kind not in self.received:
            self.received[kind] = Counter()

        self.received[kind][node_id] += 1

        if node_id in self.sink_ids and kind == "Normal":
            self.normal_latency[sequence_number] = time - self.normal_sent_time[sequence_number]
            self.normal_hop_count.append(hop_count)

    def process_SOURCE_CHANGE(self, line):
        (state, node_id) = line.strip().split(',')

        node_id = int(node_id)
        time = self.sim_time()

        if state == "set":
            self.source_ids.add(node_id)

            self.became_source_times.setdefault(node_id, []).append(time)

        elif state == "unset":
            self.source_ids.remove(node_id)

            self.became_normal_after_source_times.setdefault(node_id, []).append(time)

        else:
            raise RuntimeError("Unknown state {}".format(state))

    def seed(self):
        return self.sim.seed

    def sim_time(self):
        return self.sim.sim_time()

    def number_sent(self, name):
        return 0 if name not in self.sent else sum(self.sent[name].values())

    def number_received(self, name):
        return 0 if name not in self.received else sum(self.received[name].values())

    def total_sent(self):
        return sum(sum(sent.values()) for sent in self.sent.values())

    def total_received(self):
        return sum(sum(received.values()) for received in self.received.values())

    def sent_heat_map(self):
        return dict(sum(self.sent.values(), Counter()))

    def received_heat_map(self):
        return dict(sum(self.received.values(), Counter()))

    def average_normal_latency(self):
        return mean(self.normal_latency.values())

    def receive_ratio(self):
        return float(len(self.normal_latency)) / len(self.normal_sent_time)

    def average_sink_source_hops(self):
        return mean(self.normal_hop_count)

    def captured(self):
        return self.sim.any_attacker_found_source()

    def attacker_distance(self):
        def attacker_distance_from_src(source_id):
            source_location = self.sim.nodes[source_id].location

            return {
                i: euclidean(source_location, self.sim.nodes[attacker.position].location)
                for i, attacker
                in enumerate(self.sim.attackers)
            }

        return {
            source_id: attacker_distance_from_src(source_id)
            for source_id
            in self.source_ids
        }

    def attacker_moves(self):
        return {
            i: attacker.moves
            for i, attacker
            in enumerate(self.sim.attackers)
        }

    def node_was_source(self):
        result = {}

        for node_id in self.became_source_times.keys() + self.became_normal_after_source_times.keys():
            started_times = self.became_source_times.get(node_id, [])
            stopped_times = self.became_normal_after_source_times.get(node_id, [])

            res_lst = []

            for (start, stop) in itertools.izip_longest(started_times, stopped_times):
                if stop is None:
                    stop = float('inf')

                res_lst.append((start, stop))

            result[node_id] = res_lst

        return result

    @staticmethod
    def items():
        d = OrderedDict()
        d["Seed"]                   = lambda x: x.seed()
        d["Sent"]                   = lambda x: x.total_sent()
        d["Received"]               = lambda x: x.total_received()
        d["Collisions"]             = lambda x: None
        d["Captured"]               = lambda x: x.captured()
        d["ReceiveRatio"]           = lambda x: x.receive_ratio()
        d["TimeTaken"]              = lambda x: x.sim_time()
        d["WallTime"]               = lambda x: x.wall_time
        d["EventCount"]             = lambda x: x.event_count
        d["AttackerDistance"]       = lambda x: x.attacker_distance()
        d["AttackerMoves"]          = lambda x: x.attacker_moves()
        d["NormalLatency"]          = lambda x: x.average_normal_latency()
        d["NormalSinkSourceHops"]   = lambda x: x.average_sink_source_hops()
        d["NormalSent"]             = lambda x: x.number_sent("Normal")
        d["NodeWasSource"]          = lambda x: x.node_was_source()
        d["SentHeatMap"]            = lambda x: x.sent_heat_map()
        d["ReceivedHeatMap"]        = lambda x: x.received_heat_map()

        return d
