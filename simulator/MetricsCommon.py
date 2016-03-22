from __future__ import print_function, division

from simulator.Simulation import OutputCatcher

from collections import Counter, OrderedDict, defaultdict
import re, sys

import numpy as np

try:
    # Python 2
    from itertools import izip_longest
except ImportError:
    #Python 3
    from itertools import zip_longest as izip_longest

class MetricsCommon(object):
    def __init__(self, sim, configuration):
        self.sim = sim
        self.configuration = configuration

        self.source_ids = set(configuration.source_ids)
        self.sink_ids = {configuration.sink_id}

        self.sent = defaultdict(Counter)
        self.received = defaultdict(Counter)

        self.normal_sent_time = {}
        self.normal_latency = {}
        self.normal_hop_count = []

        self.wall_time = 0
        self.event_count = 0

        self.became_source_times = defaultdict(list)
        self.became_normal_after_source_times = defaultdict(list)

        # Normal nodes becoming the source, or source nodes becoming normal
        self.register('Metric-SOURCE_CHANGE', self.process_SOURCE_CHANGE)

        # BCAST / RCV / DELIVER events
        self.register('Metric-COMMUNICATE', self.process_COMMUNICATE)

    def register(self, name, function):
        catcher = OutputCatcher(function)
        catcher.register(self.sim, name)
        self.sim.add_output_processor(catcher)

    def process_COMMUNICATE(self, line):
        (comm_type, contents) = line.split(':', 1)

        if comm_type == 'BCAST':
            return self.process_BCAST(contents)
        elif comm_type == 'RCV':
            return self.process_RCV(contents)
        elif comm_type == 'DELIVER':
            return self.process_DELIVER(contents)
        else:
            raise RuntimeError("Unknown communication type of {}".format(comm_type))

    def process_BCAST(self, line):
        (kind, time, node_id, status, sequence_number) = line.split(',')

        if status == "success":
            time = self.sim.ticks_to_seconds(float(time))
            node_id = int(node_id)
            sequence_number = int(sequence_number)

            self.sent[kind][node_id] += 1

            if node_id in self.source_ids and kind == "Normal":
                self.normal_sent_time[(node_id, sequence_number)] = time

    def process_RCV(self, line):
        (kind, time, node_id, proximate_source_id, ultimate_source_id, sequence_number, hop_count) = line.split(',')

        time = self.sim.ticks_to_seconds(float(time))
        node_id = int(node_id)
        #proximate_source_id = int(proximate_source_id)
        ultimate_source_id = int(ultimate_source_id)
        sequence_number = int(sequence_number)
        hop_count = int(hop_count)

        self.received[kind][node_id] += 1

        if node_id in self.sink_ids and kind == "Normal":
            key = (ultimate_source_id, sequence_number)
            self.normal_latency[key] = time - self.normal_sent_time[key]
            self.normal_hop_count.append(hop_count)

    def process_DELIVER(self, line):
        pass

    #COLLSIONS_RE = re.compile(r'DEBUG\s*\((\d+)\): Lost packet from (\d+) to (\d+) due to (.*)')

    def process_COLLISIONS(self, line):
        # TODO:
        """match = self.COLLSIONS_RE.match(line)
        if match is None:
            return None

        node_id = int(match.group(1))
        node_from = int(match.group(2))
        node_to = int(match.group(3))
        reason = match.group(4)"""

        raise NotImplementedError()

    def process_SOURCE_CHANGE(self, line):
        (state, node_id) = line.strip().split(',')

        node_id = int(node_id)
        time = self.sim_time()

        if state == "set":
            self.source_ids.add(node_id)

            self.became_source_times[node_id].append(time)

        elif state == "unset":
            self.source_ids.remove(node_id)

            self.became_normal_after_source_times[node_id].append(time)

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
        # It is possible that the sink has received no Normal messages
        if len(self.normal_latency) != 0:
            return np.mean(np.fromiter(iter(self.normal_latency.values()), dtype=float))
        else:
            return float('inf')

    def receive_ratio(self):
        return len(self.normal_latency) / len(self.normal_sent_time)

    def average_sink_source_hops(self):
        # It is possible that the sink has received no Normal messages
        if len(self.normal_hop_count) != 0:
            return np.mean(self.normal_hop_count)
        else:
            return float('inf')

    def captured(self):
        return self.sim.any_attacker_found_source()

    def attacker_source_distance(self):
        return {
            (source_id, attacker.ident): self.sim.node_distance(source_id, attacker.position)

            for attacker
            in self.sim.attackers

            for source_id
            in self.source_ids
        }

    def attacker_sink_distance(self):
        return {
            (sink_id, attacker.ident): self.sim.node_distance(sink_id, attacker.position)

            for attacker
            in self.sim.attackers

            for sink_id
            in self.sink_ids
        }

    def attacker_moves(self):
        return {
            attacker.ident: attacker.moves
            for attacker
            in self.sim.attackers
        }

    def attacker_steps_towards(self):
        return {
            (source_id, attacker.ident): attacker.steps_towards[source_id]

            for attacker
            in self.sim.attackers

            for source_id
            in self.source_ids
        }

    def attacker_steps_away(self):
        return {
            (source_id, attacker.ident): attacker.steps_away[source_id]

            for attacker
            in self.sim.attackers

            for source_id
            in self.source_ids
        }

    def attacker_min_source_distance(self):
        return {
            (source_id, attacker.ident): attacker.min_source_distance[source_id]

            for attacker
            in self.sim.attackers

            for source_id
            in self.source_ids
        }


    def node_was_source(self):
        
        # No sources were detected, this may be because the code does not support this metric
        if len(self.became_source_times) == 0 and len(self.became_normal_after_source_times) == 0:
            return None

        result = {}

        nodes = set(self.became_source_times.keys())
        nodes.update(self.became_normal_after_source_times.keys())

        for node_id in nodes:
            started_times = self.became_source_times.get(node_id, [])
            stopped_times = self.became_normal_after_source_times.get(node_id, [])

            res_lst = []

            for (start, stop) in izip_longest(started_times, stopped_times):
                if stop is None:
                    stop = float('inf')

                res_lst.append((start, stop))

            result[node_id] = res_lst

        return result

    @staticmethod
    def smaller_dict_str(d):
        return str(d).replace(": ", ":").replace(", ", ",")

    @staticmethod
    def items():
        d = OrderedDict()
        d["Seed"]                          = lambda x: x.seed()
        d["Sent"]                          = lambda x: x.total_sent()
        d["Received"]                      = lambda x: x.total_received()
        d["Collisions"]                    = lambda x: None
        d["Captured"]                      = lambda x: x.captured()
        d["ReceiveRatio"]                  = lambda x: x.receive_ratio()
        d["TimeTaken"]                     = lambda x: x.sim_time()
        d["WallTime"]                      = lambda x: x.wall_time
        d["EventCount"]                    = lambda x: x.event_count
        d["AttackerDistance"]              = lambda x: x.attacker_source_distance()
        d["AttackerSinkDistance"]          = lambda x: x.attacker_sink_distance()
        d["AttackerMoves"]                 = lambda x: x.attacker_moves()
        d["AttackerStepsTowards"]          = lambda x: x.attacker_steps_towards()
        d["AttackerStepsAway"]             = lambda x: x.attacker_steps_away()
        d["AttackerMinSourceDistance"]     = lambda x: x.attacker_min_source_distance()
        d["NormalLatency"]                 = lambda x: x.average_normal_latency()
        d["NormalSinkSourceHops"]          = lambda x: x.average_sink_source_hops()
        d["NormalSent"]                    = lambda x: x.number_sent("Normal")
        d["NodeWasSource"]                 = lambda x: x.node_was_source()
        d["SentHeatMap"]                   = lambda x: MetricsCommon.smaller_dict_str(x.sent_heat_map())
        d["ReceivedHeatMap"]               = lambda x: MetricsCommon.smaller_dict_str(x.received_heat_map())

        return d

    @classmethod
    def print_header(cls, stream=sys.stdout):
        print("#" + "|".join(cls.items().keys()), file=stream)

    def print_results(self, stream=sys.stdout):
        results = [str(fn(self)) for fn in self.items().values()]
        
        print("|".join(results), file=stream)
