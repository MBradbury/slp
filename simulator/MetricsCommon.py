from __future__ import print_function, division

from collections import Counter, OrderedDict, defaultdict
import base64
import math
import zlib

try:
    # Python 2
    from itertools import izip_longest
except ImportError:
    #Python 3
    from itertools import zip_longest as izip_longest

import numpy as np

import simulator.Attacker

class MetricsCommon(object):
    def __init__(self, sim, configuration):
        self.sim = sim
        self.configuration = configuration

        self.source_ids = set() # set(configuration.source_ids)
        self.sink_ids = set() # {configuration.sink_id}

        self.sent = defaultdict(Counter)
        self.received = defaultdict(Counter)
        self.delivered = defaultdict(Counter)

        self._time_bin_width = 0.5
        self.sent_over_time = defaultdict(list)

        self.received_from_closer_or_same_hops = Counter()
        self.received_from_further_hops = Counter()
        self.received_from_closer_or_same_meters = Counter()
        self.received_from_further_meters = Counter()

        self.normal_sent_time = {}
        self.normal_latency = {}
        self.normal_hop_count = []

        self.total_wall_time = 0
        self.wall_time = 0
        self.event_count = 0

        self.became_source_times = defaultdict(list)
        self.became_normal_after_source_times = defaultdict(list)

        self.node_transitions = defaultdict(int)

        self.register('M-NC', self.process_NODE_CHANGE)

        # BCAST / RCV / DELIVER events
        self.register('M-C', self.process_COMMUNICATE)

    def _process_node_id(self, ordered_node_id):
        ordered_node_id = int(ordered_node_id)
        return ordered_node_id, self.configuration.topology.to_topo_nid(ordered_node_id)

    def register(self, name, function):
        self.sim.register_output_handler(name, function)

    def process_COMMUNICATE(self, d_or_e, node_id, time, detail):
        (comm_type, contents) = detail.split(':', 1)

        if comm_type == 'BCAST':
            return self.process_BCAST(node_id, time, contents)
        elif comm_type == 'RCV':
            return self.process_RCV(node_id, time, contents)
        elif comm_type == 'DELIV':
            return self.process_DELIVER(node_id, time, contents)
        else:
            raise RuntimeError("Unknown communication type of {}".format(comm_type))

    def _time_to_bin(self, time):
        return int(math.floor(time / self._time_bin_width))

    def process_BCAST(self, node_id, time, line):
        (kind, status, sequence_number) = line.split(',')

        # If the BCAST succeeded, then status was SUCCESS (See TinyError.h)
        if status == "0":
            ord_node_id, top_node_id = self._process_node_id(node_id)
            time = float(time)

            self.sent[kind][top_node_id] += 1

            hist = self.sent_over_time[kind]
            bin_no = self._time_to_bin(time)
            if len(hist) <= bin_no:
                hist.extend([0] * (bin_no - len(hist) + 1))
            hist[bin_no] += 1

            if ord_node_id in self.source_ids and kind == "Normal":
                sequence_number = int(sequence_number)

                # There are some times when we do not know the sequence number of the normal message
                # (See protectionless_ctp). As a -1 means a previous message is being rebroadcasted,
                # we can simply ignore adding this message
                if sequence_number != -1:
                    self.normal_sent_time[(top_node_id, sequence_number)] = time

    def process_RCV(self, node_id, time, line):
        (kind, proximate_source_id, ultimate_source_id, sequence_number, hop_count) = line.split(',')
        
        ord_node_id, top_node_id = self._process_node_id(node_id)

        self.received[kind][top_node_id] += 1

        if ord_node_id in self.sink_ids and kind == "Normal":
            time = float(time)
            ord_ultimate_source_id, top_ultimate_source_id = self._process_node_id(ultimate_source_id)
            sequence_number = int(sequence_number)
            hop_count = int(hop_count)

            # If there is a KeyError on the line with self.normal_sent_time
            # then that means that a message was received, but not recorded as sent.
            key = (top_ultimate_source_id, sequence_number)
            sent_time = self.normal_sent_time[key]
            self.normal_latency[key] = time - sent_time
            self.normal_hop_count.append(hop_count)


        # For messages the attacker responds to,
        # record whether this message was received from a node closer or further from each source
        #
        # Although source node distances are used here, we do not want to use the 
        # node_source_distance functions as when the source is mobile this code
        # will try to get a distance that the configuration doesn't believe the be a source.
        if kind not in simulator.Attacker._messages_to_ignore:
            ord_proximate_source_id, top_proximate_source_id = self._process_node_id(proximate_source_id)

            nd = self.configuration.node_distance
            ndm = self.configuration.node_distance_meters

            for ord_source_id in self.source_ids:
                prox_distance = nd(ord_proximate_source_id, ord_source_id)
                node_distance = nd(ord_node_id, ord_source_id)

                top_source_id = self.configuration.topology.to_topo_nid(ord_source_id)
                
                if node_distance < prox_distance:
                    self.received_from_further_hops[top_source_id] += 1
                else:
                    self.received_from_closer_or_same_hops[top_source_id] += 1
                
                prox_distance_m = ndm(ord_proximate_source_id, ord_source_id)
                node_distance_m = ndm(ord_node_id, ord_source_id)
                
                if node_distance_m < prox_distance_m:
                    self.received_from_further_meters[top_source_id] += 1
                else:
                    self.received_from_closer_or_same_meters[top_source_id] += 1

    def process_DELIVER(self, node_id, time, line):
        (kind, proximate_source_id, ultimate_source_id, sequence_number) = line.split(',')

        ord_node_id, top_node_id = self._process_node_id(node_id)

        self.delivered[kind][top_node_id] += 1

    def process_NODE_CHANGE(self, d_or_e, node_id, time, detail):
        (old_name, new_name) = detail.split(',')

        ord_node_id, top_node_id = self._process_node_id(node_id)
        time = float(time)

        if new_name == "SourceNode":
            self.source_ids.add(ord_node_id)

            self.became_source_times[top_node_id].append(time)

            for attacker in self.sim.attackers:
                attacker.handle_metrics_new_source(ord_node_id)

        elif old_name == "SourceNode":
            self.source_ids.remove(ord_node_id)

            self.became_normal_after_source_times[top_node_id].append(time)

        if new_name == "SinkNode":
            if old_name != "<unknown>":
                raise RuntimeError("SinkNodes MUST be created from no initial node type but was instead from {}".format(old_name))

            self.sink_ids.add(ord_node_id)

        self.node_transitions[(old_name, new_name)] += 1



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

    def total_delivered(self):
        return sum(sum(delivered.values()) for delivered in self.delivered.values())

    def sent_heat_map(self):
        return dict(sum(self.sent.values(), Counter()))

    def received_heat_map(self):
        return dict(sum(self.received.values(), Counter()))

    def first_normal_sent_time(self):
        return min(normal_sent_time.values())

    def average_normal_latency(self):
        # It is possible that the sink has received no Normal messages
        if len(self.normal_latency) != 0:
            return np.mean(np.fromiter(iter(self.normal_latency.values()), dtype=float))
        else:
            return float('inf')

    def receive_ratio(self):
        # The receive ratio may be end up being lower than it actually is
        # if a simple division is performed below.
        #
        # It may be the case that an attacker captures the source
        # before a message has a chance to reach the sink.
        # For example, if an attacker is directly next to the source,
        # the next message will be considered lost.
        # 
        # By checking if the simulation finish time is almost equal to
        # the last message send time, we can find out if there is a
        # message that never had a chance to be received and thus discount it.
        #
        # The simulation will not usually finish at exactly the same time that
        # the last message was sent (because it takes time to receive a message),
        # so a small tolerance value is used.

        end_time = self.sim_time()
        send_modifier = 0

        if len(self.normal_sent_time) > 0 and np.isclose(max(self.normal_sent_time.values()), end_time, atol=0.07):
            send_modifier = 1

        return len(self.normal_latency) / (len(self.normal_sent_time) - send_modifier)

    def average_sink_source_hops(self):
        # It is possible that the sink has received no Normal messages
        if len(self.normal_hop_count) != 0:
            return np.mean(self.normal_hop_count)
        else:
            return float('inf')

    def captured(self):
        return self.sim.any_attacker_found_source()

    def attacker_source_distance(self):
        ttn = self.configuration.topology.to_topo_nid
        ndm = self.configuration.node_distance_meters

        return {
            (ttn(ord_source_id), attacker.ident): ndm(ord_source_id, attacker.position)

            for attacker
            in self.sim.attackers

            for ord_source_id
            in self.source_ids
        }

    def attacker_sink_distance(self):
        ttn = self.configuration.topology.to_topo_nid
        ndm = self.configuration.node_distance_meters

        return {
            (ttn(ord_sink_id), attacker.ident): ndm(ord_sink_id, attacker.position)

            for attacker
            in self.sim.attackers

            for ord_sink_id
            in self.sink_ids
        }

    def attacker_moves(self):
        return {
            attacker.ident: attacker.moves
            for attacker
            in self.sim.attackers
        }

    def attacker_moves_in_response_to(self):
        return {
            attacker.ident: dict(attacker.moves_in_response_to)
            for attacker
            in self.sim.attackers
        }

    def attacker_steps_towards(self):
        ttn = self.configuration.topology.to_topo_nid

        return {
            (ttn(ord_source_id), attacker.ident): attacker.steps_towards[ord_source_id]

            for attacker
            in self.sim.attackers

            for ord_source_id
            in self.source_ids
        }

    def attacker_steps_away(self):
        ttn = self.configuration.topology.to_topo_nid

        return {
            (ttn(ord_source_id), attacker.ident): attacker.steps_away[ord_source_id]

            for attacker
            in self.sim.attackers

            for ord_source_id
            in self.source_ids
        }

    def attacker_min_source_distance(self):
        ttn = self.configuration.topology.to_topo_nid

        return {
            (ttn(ord_source_id), attacker.ident): attacker.min_source_distance[ord_source_id]

            for attacker
            in self.sim.attackers

            for ord_source_id
            in self.source_ids
        }


    def node_was_source(self):
        
        # No sources were detected, this may be because the code does not support this metric
        if len(self.became_source_times) == 0 and len(self.became_normal_after_source_times) == 0:
            return None

        result = {}

        nodes = set(self.became_source_times.keys())
        nodes.update(self.became_normal_after_source_times.keys())

        for top_node_id in nodes:
            started_times = self.became_source_times.get(top_node_id, [])
            stopped_times = self.became_normal_after_source_times.get(top_node_id, [])

            res_lst = []

            for (start, stop) in izip_longest(started_times, stopped_times):
                if stop is None:
                    stop = float('inf')

                res_lst.append((start, stop))

            result[top_node_id] = res_lst

        return result

    def times_node_changed_to(self, node_type, from_types=None):
        total_count = 0

        for ((old_type, new_type), count) in self.node_transitions.items():

            # Ignore some source types
            if from_types is not None:
                if old_type not in from_types:
                    continue

            if new_type == node_type:
                total_count += count

        return total_count

    @staticmethod
    def smaller_dict_str(d):
        return str(d).replace(": ", ":").replace(", ", ",")

    @staticmethod
    def compressed_dict_str(d):
        d = MetricsCommon.smaller_dict_str(d)
        return base64.b64encode(zlib.compress(d, 9))

    @staticmethod
    def items():
        d = OrderedDict()
        d["Seed"]                          = lambda x: x.seed()
        d["Sent"]                          = lambda x: x.total_sent()
        d["Received"]                      = lambda x: x.total_received()
        d["Delivered"]                     = lambda x: x.total_delivered()
        d["Collisions"]                    = lambda x: None
        d["Captured"]                      = lambda x: x.captured()
        d["ReceiveRatio"]                  = lambda x: x.receive_ratio()
        d["FirstNormalSentTime"]           = lambda x: x.first_normal_sent_time()
        d["TimeTaken"]                     = lambda x: x.sim_time()
        d["WallTime"]                      = lambda x: x.wall_time
        d["TotalWallTime"]                 = lambda x: x.total_wall_time
        d["EventCount"]                    = lambda x: x.event_count
        d["AttackerDistance"]              = lambda x: x.attacker_source_distance()
        d["AttackerSinkDistance"]          = lambda x: x.attacker_sink_distance()
        d["AttackerMoves"]                 = lambda x: x.attacker_moves()
        d["AttackerMovesInResponseTo"]     = lambda x: x.attacker_moves_in_response_to()
        d["AttackerStepsTowards"]          = lambda x: x.attacker_steps_towards()
        d["AttackerStepsAway"]             = lambda x: x.attacker_steps_away()
        d["AttackerMinSourceDistance"]     = lambda x: x.attacker_min_source_distance()
        d["NormalLatency"]                 = lambda x: x.average_normal_latency()
        d["NormalSinkSourceHops"]          = lambda x: x.average_sink_source_hops()
        d["NormalSent"]                    = lambda x: x.number_sent("Normal")
        d["NodeWasSource"]                 = lambda x: x.node_was_source()
        d["NodeTransitions"]               = lambda x: MetricsCommon.smaller_dict_str(dict(x.node_transitions))
        d["SentHeatMap"]                   = lambda x: MetricsCommon.compressed_dict_str(x.sent_heat_map())
        d["ReceivedHeatMap"]               = lambda x: MetricsCommon.compressed_dict_str(x.received_heat_map())

        d["TimeBinWidth"]                  = lambda x: x._time_bin_width
        d["SentOverTime"]                  = lambda x: MetricsCommon.smaller_dict_str(dict(x.sent_over_time))

        d["ReceivedFromCloserOrSameHops"]  = lambda x: MetricsCommon.smaller_dict_str(dict(x.received_from_closer_or_same_hops))
        d["ReceivedFromFurtherHops"]       = lambda x: MetricsCommon.smaller_dict_str(dict(x.received_from_further_hops))
        d["ReceivedFromCloserOrSameMeters"]= lambda x: MetricsCommon.smaller_dict_str(dict(x.received_from_closer_or_same_meters))
        d["ReceivedFromFurtherMeters"]     = lambda x: MetricsCommon.smaller_dict_str(dict(x.received_from_further_meters))

        return d

    @classmethod
    def print_header(cls, stream=None):
        """Print the results header to the specified stream (defaults to sys.stdout)."""
        print("#" + "|".join(cls.items().keys()), file=stream)

    def get_results(self):
        """Get the results in the result file format."""
        return "|".join(str(fn(self)) for fn in self.items().values())

    def print_results(self, stream=None):
        """Print the results to the specified stream (defaults to sys.stdout)."""
        try:
            print(self.get_results(), file=stream)
        except Exception as ex:
            import traceback
            raise RuntimeError("Failed to get the result string for seed {} (events={}, sim_time={}) caused by {}".format(
                self.seed(), self.event_count, self.sim_time(), traceback.format_exc())
            )
