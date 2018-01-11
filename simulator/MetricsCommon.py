from __future__ import print_function, division

from collections import Counter, OrderedDict, defaultdict, namedtuple
import base64
from itertools import zip_longest, tee
import math
import pickle
import struct
import sys
import zlib

# Allow missing psutil
try:
    import psutil
except ImportError:
    psutil = None

import numpy as np

import simulator.Attacker
from simulator.Topology import OrderedId

from data.util import RunningStats

AM_BROADCAST_ADDR = 65535

# From: https://docs.python.org/3/library/itertools.html#recipes
def pairwise(iterable):
    """s -> (s0,s1), (s1,s2), (s2, s3), ..."""
    a, b = tee(iterable, 2)
    next(b, None)
    return zip(a, b)

def message_type_to_colour(kind):
    return {
        "Normal": "blue",
        "Fake": "red",
        "Away": "magenta",
        "Choose": "green",
        "Notify": "cyan",
        "Beacon": "black",
        "Poll": "xkcd:orange",
    }[kind]

def node_type_to_colour(kind):
    return {
        "NormalNode": "dodgerblue",
        "TempFakeNode": "olive",
        "TailFakeNode": "gold",
        "PermFakeNode": "darkorange",
        "SourceNode": "darkgreen",
        "SinkNode": "darkblue",
    }[kind]

class MetricsCommon(object):
    def __init__(self, sim, configuration, strict=True):
        super().__init__()

        self.sim = sim
        self.configuration = configuration
        self.topology = configuration.topology

        self.strict = strict

        self._message_parsers = {}

        self.reported_source_ids = set() # set(configuration.source_ids)
        self.reported_sink_ids = set() # {configuration.sink_id}

        self.node_booted_at = defaultdict(list)

        self.sent = defaultdict(Counter)
        self.received = defaultdict(Counter)
        self.delivered = defaultdict(Counter)

        self.messages_broadcast = OrderedDict()

        self._time_bin_width = 0.5
        self.sent_over_time = defaultdict(list)

        self.received_from_closer_or_same_hops = defaultdict(Counter)
        self.received_from_further_hops = defaultdict(Counter)
        self.received_from_closer_or_same_meters = defaultdict(Counter)
        self.received_from_further_meters = defaultdict(Counter)

        self.delivered_from_closer_or_same_hops = defaultdict(Counter)
        self.delivered_from_further_hops = defaultdict(Counter)
        self.delivered_from_closer_or_same_meters = defaultdict(Counter)
        self.delivered_from_further_meters = defaultdict(Counter)

        self.normal_sent_time = OrderedDict()
        self.normal_receive_time = OrderedDict()
        self.normal_latency = {}
        self.normal_hop_count = []

        self.receive_time = {}

        self.total_wall_time = None
        self.wall_time = None
        self.event_count = None

        self.errors = Counter()

        self.became_source_times = defaultdict(list)
        self.became_normal_after_source_times = defaultdict(list)

        self.node_transitions = defaultdict(int)

        self.node_types = {}
        self.message_types = {}

        self.delivered_rssi = defaultdict(RunningStats)
        self.delivered_lqi = defaultdict(RunningStats)

        self._generic_handlers = {}

        self.register('M-B', self.process_node_booted)
        self.register('M-G', self.process_generic)
        self.register('M-NC', self.process_node_change_event)

        self.register('M-NTA', self.process_node_type_add)
        self.register('M-MTA', self.process_message_type_add)

        # BCAST / RCV / DELIVER events
        self.register('M-CB', self.process_bcast_event)
        self.register('M-CR', self.process_rcv_event)
        self.register('M-CD', self.process_deliver_event)

        self.register('stderr', self.process_error_event)

        if not self.strict:
            self._non_strict_setup()

    def _non_strict_setup(self):
        """Set up any variables that may be missing in non-strict cases.
        For example testbed serial aggregators may miss important info."""
        import os.path
        import re

        # Find the node and message, name and name associations
        source_dir = self.sim.module_name.replace(".", "/")

        register_pair = re.compile(r"call (MessageType|NodeType)\.register_pair\(([A-Za-z_]+), \"([A-Za-z]+)\"\)")

        matches = []
        names_assoc = {}

        with open(os.path.join(source_dir, 'SourceBroadcasterC.nc'), "r") as source_file:
            for line in source_file:
                match = register_pair.findall(line)
                if match:
                    matches.extend(match)

        # Find the variable values
        names = "|".join(var_name for (kind, var_name, str_name) in matches)

        register_pair = re.compile(r"({})\s*=\s*([0-9]+)".format(names))

        with open(os.path.join(source_dir, 'Constants.h'), "r") as source_file:
            for line in source_file:
                match = register_pair.findall(line)
                if match:
                    for (name, value) in match:
                        names_assoc[name] = int(value)

        # Set the types
        for (kind, var_name, str_name) in matches:
            var = names_assoc[var_name]

            if kind == "MessageType":
                self.message_types[var] = str_name

            elif kind == "NodeType":
                self.node_types[var] = str_name

            else:
                assert False

    def finish(self):
        """Called when the simulation has finished.
        Perform any post simulation actions here."""
        pass

    def source_ids(self):
        if self.strict:
            return self.reported_source_ids
        else:
            return set(self.configuration.source_ids)

    def sink_ids(self):
        if self.strict:
            return self.reported_sink_ids
        else:
            return set(self.configuration.sink_ids)

    def _process_node_id(self, ordered_node_id):
        if int(ordered_node_id) == AM_BROADCAST_ADDR:
            return None, None

        ordered_node_id = OrderedId(int(ordered_node_id))
        return ordered_node_id, self.topology.o2t(ordered_node_id)

    def register(self, name, function):
        """Register a callback :function: for the event with name :name:"""
        self.sim.register_output_handler(name, function)

    def register_generic(self, identifier, function):
        """Register a callback for a generic event."""
        self._generic_handlers[identifier] = function


    def add_message_format(self, message_name, parse_string, content_names):
        """Adds a message format record, that can be used to parse the hex buffer of the message."""
        content_names = list(content_names)
        content_names.append("crc")

        message_name_cls = namedtuple(message_name, " ".join(content_names))
        message_name_cls.__new__.__default__ = (None,) * len(content_names)

        self._message_parsers[message_name] = (parse_string, message_name_cls)

    def parse_message(self, message_name, hex_buffer):
        """Builds a data structure from the hex buffer of a message."""
        (parse_string, message_name_cls) = self._message_parsers[message_name]

        buf = bytes.fromhex(hex_buffer)

        if struct.calcsize(parse_string) == len(buf):
            contents = struct.unpack(parse_string, buf)
        else:
            # Try parsing with a crc uint16_t
            contents = struct.unpack(parse_string + "H", buf)

        return message_name_cls._make(contents)


    def _time_to_bin(self, time):
        return int(math.floor(time / self._time_bin_width))


    def message_kind_to_string(self, kind):
        try:
            return self.message_types[int(kind)]
        except ValueError:
            return kind

    def node_kind_to_string(self, kind):
        try:
            return self.node_types[int(kind)]
        except ValueError:
            return kind

    def parse_sequence_number(self, sequence_number):
        sequence_number = int(sequence_number)
        if sequence_number >= 0:
            return sequence_number
        elif sequence_number == -1:
            return None
        else:
            self._warning_or_error(f"The sequence number is an invalid unknown of {sequence_number}")
            return None

    def process_node_type_add(self, d_or_e, node_id, time, detail):
        (ident, name) = detail.split(',')
        self.node_types[int(ident)] = name

    def process_message_type_add(self, d_or_e, node_id, time, detail):
        (ident, name) = detail.split(',')
        self.message_types[int(ident)] = name

    def _warning_or_error(self, message):
        if self.strict:
            raise RuntimeError(message)
        else:
            print("WARNING:", message, file=sys.stderr)



    def process_bcast_event(self, d_or_e, node_id, time, detail):
        try:
            (kind, status, ultimate_source_id, sequence_number, tx_power, hex_buffer) = detail.split(',')
        except ValueError:
            (kind, status, sequence_number, tx_power) = detail.split(',')
            ultimate_source_id = None

        # If the BCAST succeeded, then status was SUCCESS (See TinyError.h)
        if status != "0":
            return

        key = (str(node_id), kind, ultimate_source_id, sequence_number)
        if key not in self.messages_broadcast:
            self.messages_broadcast[key] = list()
        self.messages_broadcast[key].append(hex_buffer)

        ord_node_id, top_node_id = self._process_node_id(node_id)
        time = float(time)

        kind = self.message_kind_to_string(kind)

        self.sent[kind][top_node_id] += 1

        hist = self.sent_over_time[kind]
        bin_no = self._time_to_bin(time)
        if len(hist) <= bin_no:
            hist.extend([0] * (bin_no - len(hist) + 1))
        hist[bin_no] += 1

        if ord_node_id in self.source_ids() and kind == "Normal":
            sequence_number = self.parse_sequence_number(sequence_number)

            # There are some times when we do not know the sequence number of the normal message
            # (See protectionless_ctp). As a -1 means a previous message is being rebroadcasted,
            # we can simply ignore adding this message
            if sequence_number is not None:
                self.normal_sent_time[(top_node_id, sequence_number)] = time

                # Handle starting the duration timeout in the simulation running
                self.sim.trigger_duration_run_start(time)

        if __debug__:
            if kind == "Normal" and ultimate_source_id is not None:
                try:
                    ord_ultimate_source_id, top_ultimate_source_id = self._process_node_id(ultimate_source_id)
                    if ord_ultimate_source_id not in self.source_ids():
                        self._warning_or_error("Node {} bcast a Normal message from {} which is not a source id ({}). Detail: {}".format(
                            node_id, ord_ultimate_source_id, self.source_ids(), detail))
                except KeyError:
                    self._warning_or_error("Node {} bcast a Normal message from {} which is not a valid ordered node id. Detail: {}".format(
                            node_id, ultimate_source_id, detail))

    def _record_direction_received(self, kind, ord_node_id, ord_proximate_source_id,
                                   further_hops, closer_or_same_hops,
                                   further_meters, closer_or_same_meters):
        # For messages the attacker responds to,
        # record whether this message was received from a node closer or further from each source
        #
        # Although source node distances are used here, we do not want to use the 
        # node_source_distance functions as when the source is mobile this code
        # will try to get a distance that the configuration doesn't believe the be a source.
        if kind in simulator.Attacker.MESSAGES_TO_IGNORE:
            return

        conf = self.configuration
        topo = conf.topology

        o2i = topo.o2i
        o2t = topo.o2t

        idx_proximate_source_id = o2i(ord_proximate_source_id).nid
        idx_node_id = o2i(ord_node_id).nid

        nd = conf._dist_matrix
        ndm = conf._dist_matrix_meters

        for ord_source_id in self.source_ids():
            top_source_id = o2t(ord_source_id)
            idx_source_id = o2i(ord_source_id).nid

            # Not all topologies know the distance in hops
            if nd is not None:
                prox_distance = nd[idx_source_id, idx_proximate_source_id]
                node_distance = nd[idx_source_id, idx_node_id]
                
                if node_distance < prox_distance:
                    further_hops[kind][top_source_id] += 1
                else:
                    closer_or_same_hops[kind][top_source_id] += 1
            
            prox_distance_m = ndm[idx_source_id, idx_proximate_source_id]
            node_distance_m = ndm[idx_source_id, idx_node_id]
            
            if node_distance_m < prox_distance_m:
                further_meters[kind][top_source_id] += 1
            else:
                closer_or_same_meters[kind][top_source_id] += 1

    def process_rcv_event(self, d_or_e, node_id, time, detail):
        (kind, proximate_source_id, ultimate_source_id, sequence_number, hop_count) = detail.split(',')

        ord_node_id, top_node_id = self._process_node_id(node_id)

        time = float(time)
        kind = self.message_kind_to_string(kind)
        sequence_number = self.parse_sequence_number(sequence_number)
        ord_ultimate_source_id, top_ultimate_source_id = self._process_node_id(ultimate_source_id)

        self.received[kind][top_node_id] += 1

        if ord_node_id in self.sink_ids() and kind == "Normal":
            hop_count = int(hop_count)

            # If there is a KeyError on the line with self.normal_sent_time
            # then that means that a message was received, but not recorded as sent.
            key = (top_ultimate_source_id, sequence_number)

            try:
                sent_time = self.normal_sent_time[key]
                self.normal_latency[key] = time - sent_time
            except KeyError as ex:
                if not self.strict:
                    print("Unable to find the normal sent time for key {}.".format(key), file=sys.stderr)
                    self.normal_latency[key] = None
                else:
                    raise

            self.normal_receive_time[key] = time
            self.normal_hop_count.append(hop_count)

        ord_proximate_source_id, top_proximate_source_id = self._process_node_id(proximate_source_id)

        self._record_direction_received(kind, ord_node_id, ord_proximate_source_id,
                                        self.received_from_further_hops, self.received_from_closer_or_same_hops,
                                        self.received_from_further_meters, self.received_from_closer_or_same_meters)

        #self.receive_time.setdefault(kind, {}).setdefault(ord_node_id, OrderedDict())[(ord_ultimate_source_id, sequence_number)] = time
        self.receive_time.setdefault(kind, {}).setdefault(ord_node_id, []).append(time)

    def process_deliver_event(self, d_or_e, node_id, time, detail):
        try:
            (kind, target, proximate_source_id, ultimate_source_id, sequence_number, rssi, lqi, hex_buffer) = detail.split(',')
        except ValueError:
            (kind, proximate_source_id, ultimate_source_id, sequence_number, rssi, lqi) = detail.split(',')

        if __debug__:
            try:
                sent_hex_buffers = self.messages_broadcast[(proximate_source_id, kind, ultimate_source_id, sequence_number)]

                if all(sent_hex_buffer != hex_buffer for sent_hex_buffer in sent_hex_buffers):
                    sent_hex_buffer_str = "\n".join(f"\t{sent_hex_buffer}" for sent_hex_buffer in sent_hex_buffers)

                    raise RuntimeError("The received hex buffer does not match any sent buffer for prox-src={}, kind={}, ult-src={}, seq-no={}\nSent:\n{}\nReceived:\n\t{}".format(
                        proximate_source_id, kind, ultimate_source_id, sequence_number,
                        sent_hex_buffer_str,
                        hex_buffer))

            except KeyError as ex:
                print("Received {} but unable to find a matching key".format(hex_buffer), file=sys.stderr)
                for (k, v) in self.messages_broadcast.items():
                    print(f"{k}: {v}", file=sys.stderr)
                raise

        ord_node_id, top_node_id = self._process_node_id(node_id)
        ord_prox_src_id, top_prox_src_id = self._process_node_id(proximate_source_id)

        kind = self.message_kind_to_string(kind)
        sequence_number = self.parse_sequence_number(sequence_number)

        self.delivered[kind][top_node_id] += 1

        self._record_direction_received(kind, ord_node_id, ord_prox_src_id,
                                        self.delivered_from_further_hops, self.delivered_from_closer_or_same_hops,
                                        self.delivered_from_further_meters, self.delivered_from_closer_or_same_meters)

        key = (top_prox_src_id, top_node_id)

        self.delivered_rssi[key].push(int(rssi))
        self.delivered_lqi[key].push(int(lqi))

        # Check that the normal message that has been delivered has a ultimate source
        # that we believe to be a source.
        if __debug__:
            if kind == "Normal":
                try:
                    ord_ultimate_source_id, top_ultimate_source_id = self._process_node_id(ultimate_source_id)
                    if ord_ultimate_source_id not in self.source_ids():
                        self._warning_or_error("Node {} received a Normal message from {} which is not a source id ({}). Detail: {}".format(
                            node_id, ord_ultimate_source_id, self.source_ids(), detail))
                except KeyError:
                    self._warning_or_error("Node {} received a Normal message from {} which is not a valid ordered node id. Detail: {}".format(
                            node_id, ultimate_source_id, detail))

    def process_node_booted(self, d_or_e, node_id, time, detail):
        ord_node_id, top_node_id = self._process_node_id(node_id)
        self.node_booted_at[ord_node_id].append(float(time))

    def process_generic(self, d_or_e, node_id, time, detail):
        (kind, data) = detail.split(",", 1)
        kind = int(kind)

        handler = self._generic_handlers.get(kind, None)

        if handler is None:
            return

        handler(d_or_e, node_id, time, data)

    def process_node_change_event(self, d_or_e, node_id, time, detail):
        (old_name, new_name) = detail.split(',')

        ord_node_id, top_node_id = self._process_node_id(node_id)
        time = float(time)

        if new_name == "SourceNode":
            self.reported_source_ids.add(ord_node_id)

            self.became_source_times[top_node_id].append(time)

            for attacker in self.sim.attackers:
                attacker.handle_metrics_new_source(ord_node_id)

        elif old_name == "SourceNode":
            self.reported_source_ids.remove(ord_node_id)

            self.became_normal_after_source_times[top_node_id].append(time)

        if new_name == "SinkNode":
            if old_name != "<unknown>":
                raise RuntimeError(f"SinkNodes MUST be created from no initial node type but was instead from {old_name}")

            self.reported_sink_ids.add(ord_node_id)

        self.node_transitions[(old_name, new_name)] += 1

    def process_error_event(self, d_or_e, node_id, time, detail):
        (code, message) = detail.split(",", 1)

        code = int(code)

        self.errors[code] += 1


    def num_normal_sent_if_finished(self):
        if self.reached_sim_upper_bound() and len(self.normal_sent_time) == 0:
            return float('NaN')
        else:
            return len(self.normal_sent_time)


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
        try:
            return min(self.normal_sent_time.values())
        except ValueError:
            return float('NaN')

    def average_normal_latency(self):
        non_null_latency = [x for x in self.normal_latency.values() if x is not None]

        # It is possible that the sink has received no Normal messages
        if len(non_null_latency) != 0:
            return np.mean(np.fromiter(iter(non_null_latency), dtype=float))
        else:
            return float('inf')

    def maximum_normal_latency(self):
        non_null_latency = [x for x in self.normal_latency.values() if x is not None]

        if len(non_null_latency) != 0:
            return max(non_null_latency)
        else:
            return float('inf')

    def minimum_normal_latency(self):
        non_null_latency = [x for x in self.normal_latency.values() if x is not None]

        if len(non_null_latency) != 0:
            return min(non_null_latency)
        else:
            return float('inf')

    def normal_inter_arrival_time(self):
        items = self.normal_receive_time.values()

        return [btime - atime for atime, btime in pairwise(items)]

    def normal_inter_arrival_time_average(self):
        iat = self.normal_inter_arrival_time()

        if len(iat) > 0:
            return np.mean(iat)
        else:
            return float('inf')

    def normal_inter_arrival_time_variance(self):
        iat = self.normal_inter_arrival_time()

        if len(iat) > 0:
            return np.var(iat)
        else:
            return float('inf')

    def normal_inter_generation_time(self):
        items = self.normal_sent_time.values()

        return [btime - atime for atime, btime in pairwise(items)]

    def normal_inter_generation_time_average(self):
        igt = self.normal_inter_generation_time()

        if len(igt) > 0:
            return np.mean(igt)
        else:
            return float('inf')

    def normal_inter_generation_time_variance(self):
        igt = self.normal_inter_generation_time()

        if len(igt) > 0:
            return np.var(igt)
        else:
            return float('inf')

    def message_receive_interval(self):
        #self.receive_time.setdefault(kind, {}).setdefault(ord_node_id, {})[(ord_ultimate_source_id, sequence_number)] = time

        return {
            kind: {
                nid: round(np.mean([b - a for (a, b) in pairwise(values1)]), 6)

                for (nid, values1) in values.items()
            }
            for (kind, values) in self.receive_time.items()
        }


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

        if len(set(self.normal_receive_time.keys()) - set(self.normal_sent_time.keys())) > 0:
            raise RuntimeError("We received an unexpected message (sent: {}) (received {})!".format(
                self.normal_sent_time, self.normal_receive_time
            ))

        if len(self.normal_sent_time) == 0:
            return float('NaN')

        if len(self.normal_receive_time) == len(self.normal_sent_time):
            return 1.0

        end_time = self.sim_time()
        send_modifier = 0

        if len(self.normal_sent_time) > 1 and np.isclose(max(self.normal_sent_time.values()), end_time, atol=0.07):
            send_modifier = 1

        return len(self.normal_receive_time) / (len(self.normal_sent_time) - send_modifier)

    def attacker_receive_ratio(self, attacker):

        if len(self.normal_sent_time) == 0:
            return float('NaN')

        return len(attacker.normal_receive_time) / len(self.normal_sent_time)

    def attackers_receive_ratio(self):
        return {
            attacker.ident: self.attacker_receive_ratio(attacker)
            for attacker
            in self.sim.attackers
        }

    def average_sink_source_hops(self):
        # It is possible that the sink has received no Normal messages
        if len(self.normal_hop_count) != 0:
            return np.mean(self.normal_hop_count)
        else:
            return float('inf')

    def captured(self):
        return self.sim.any_attacker_found_source()

    def attacker_source_distance(self):
        o2t = self.topology.o2t
        ndm = self.configuration.node_distance_meters

        return {
            (o2t(ord_source_id), attacker.ident): ndm(ord_source_id, attacker.position)

            for attacker
            in self.sim.attackers

            for ord_source_id
            in self.source_ids()
        }

    def attacker_sink_distance(self):
        o2t = self.topology.o2t
        ndm = self.configuration.node_distance_meters

        return {
            (o2t(ord_sink_id), attacker.ident): ndm(ord_sink_id, attacker.position)

            for attacker
            in self.sim.attackers

            for ord_sink_id
            in self.sink_ids()
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
        o2t = self.topology.o2t

        return {
            (o2t(ord_source_id), attacker.ident): attacker.steps_towards[ord_source_id]

            for attacker
            in self.sim.attackers

            for ord_source_id
            in self.source_ids()
        }

    def attacker_steps_away(self):
        o2t = self.topology.o2t

        return {
            (o2t(ord_source_id), attacker.ident): attacker.steps_away[ord_source_id]

            for attacker
            in self.sim.attackers

            for ord_source_id
            in self.source_ids()
        }

    def attacker_min_source_distance(self):
        o2t = self.topology.o2t

        return {
            (o2t(ord_source_id), attacker.ident): attacker.min_source_distance[ord_source_id]

            for attacker
            in self.sim.attackers

            for ord_source_id
            in self.source_ids()
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

            for (start, stop) in zip_longest(started_times, stopped_times):
                if stop is None:
                    stop = float('inf')

                res_lst.append((start, stop))

            result[top_node_id] = res_lst

        return result

    def times_node_changed_to(self, node_type, from_types=None):
        total_count = 0

        if not isinstance(node_type, (tuple, list)):
            node_type = (node_type,)

        if from_types is not None:
            if not isinstance(from_types, (tuple, list)):
                from_types = (from_types,) 

        for ((old_type, new_type), count) in self.node_transitions.items():

            # Ignore some source types
            if from_types is not None:
                if old_type not in from_types:
                    continue

            if new_type in node_type:
                total_count += count

        return total_count

    def reached_sim_upper_bound(self):
        if not hasattr(self.sim, "upper_bound_safety_period"):
            return False
        else:
            return self.sim_time() >= self.sim.upper_bound_safety_period

    def detected_boot_events(self):
        return len(self.node_booted_at)

    def detected_boot_events_total(self):
        return sum(len(l) for l in self.node_booted_at.values())


    def rcvd_closer_or_same_hops_all(self):
        return dict(sum(self.received_from_closer_or_same_hops.values(), Counter()))

    def rcvd_further_hops_all(self):
        return dict(sum(self.received_from_further_hops.values(), Counter()))

    def rcvd_closer_or_same_meters_all(self):
        return dict(sum(self.received_from_closer_or_same_meters.values(), Counter()))

    def rcvd_further_meters_all(self):
        return dict(sum(self.received_from_further_meters.values(), Counter()))

    def rcvd_closer_or_same_hops(self, msg):
        return dict(self.received_from_closer_or_same_hops[msg])

    def rcvd_further_hops(self, msg):
        return dict(self.received_from_further_hops[msg])

    def rcvd_closer_or_same_meters(self, msg):
        return dict(self.received_from_closer_or_same_meters[msg])

    def rcvd_further_meters(self, msg):
        return dict(self.received_from_further_meters[msg])



    def deliv_closer_or_same_hops_all(self):
        return dict(sum(self.delivered_from_closer_or_same_hops.values(), Counter()))

    def deliv_further_hops_all(self):
        return dict(sum(self.delivered_from_further_hops.values(), Counter()))

    def deliv_closer_or_same_meters_all(self):
        return dict(sum(self.delivered_from_closer_or_same_meters.values(), Counter()))

    def deliv_further_meters_all(self):
        return dict(sum(self.delivered_from_further_meters.values(), Counter()))

    def deliv_closer_or_same_hops(self, msg):
        return dict(self.delivered_from_closer_or_same_hops[msg])

    def deliv_further_hops(self, msg):
        return dict(self.delivered_from_further_hops[msg])

    def deliv_closer_or_same_meters(self, msg):
        return dict(self.delivered_from_closer_or_same_meters[msg])

    def deliv_further_meters(self, msg):
        return dict(self.delivered_from_further_meters[msg])


    def faults_occurred(self):
        return self.sim.fault_model.faults_occurred

    def delivered_rssi_stats(self):
        return {
            key: (value.mean(), value.stddev(), value.n)
            for (key, value)
            in self.delivered_rssi.items()
        }

    def delivered_lqi_stats(self):
        return {
            key: (value.mean(), value.stddev(), value.n)
            for (key, value)
            in self.delivered_lqi.items()
            if value.mean() != -1
        }

    @staticmethod
    def sorted_dict_str(dict_result):
        return "{" + ", ".join(f"{k}: {v}" for (k, v) in sorted(dict_result.items(), key=lambda x: x[0])) + "}"

    @staticmethod
    def smaller_dict_str(dict_result, sort=False):
        dict_str = MetricsCommon.sorted_dict_str(dict_result) if sort else str(dict_result)

        return dict_str.replace(": ", ":").replace(", ", ",").replace(".0,", ",")

    @staticmethod
    def compressed_dict_str(dict_result, sort=False):
        dict_result_bytes = MetricsCommon.smaller_dict_str(dict_result, sort=sort).encode("utf-8")
        compressed = base64.b64encode(zlib.compress(dict_result_bytes, 9))
        return compressed.decode("utf-8")

    @staticmethod
    def smaller_list_str(list_result):
        return str(list_result).replace(", ", ",")

    @staticmethod
    def items():
        d = OrderedDict()
        d["Seed"]                          = lambda x: x.seed()

        # Core metrics
        d["Sent"]                          = lambda x: x.total_sent()
        d["Received"]                      = lambda x: x.total_received()
        d["Delivered"]                     = lambda x: x.total_delivered()
        #d["Collisions"]                    = lambda x: None
        d["Captured"]                      = lambda x: x.captured()
        d["ReachedSimUpperBound"]          = lambda x: x.reached_sim_upper_bound()
        d["ReceiveRatio"]                  = lambda x: x.receive_ratio()
        d["FirstNormalSentTime"]           = lambda x: x.first_normal_sent_time()
        d["TimeTaken"]                     = lambda x: x.sim_time()

        # Performance metrics of the simulator
        d["WallTime"]                      = lambda x: x.wall_time
        d["TotalWallTime"]                 = lambda x: x.total_wall_time
        d["EventCount"]                    = lambda x: x.event_count
        d["MemoryRSS"]                     = lambda x: str(x.memory_info("rss"))
        d["MemoryVMS"]                     = lambda x: str(x.memory_info("vms"))

        # Attacker metrics
        d["AttackerDistance"]              = lambda x: x.attacker_source_distance()
        d["AttackerSinkDistance"]          = lambda x: x.attacker_sink_distance()
        d["AttackerMoves"]                 = lambda x: x.attacker_moves()
        d["AttackerMovesInResponseTo"]     = lambda x: x.attacker_moves_in_response_to()
        d["AttackerStepsTowards"]          = lambda x: x.attacker_steps_towards()
        d["AttackerStepsAway"]             = lambda x: x.attacker_steps_away()
        d["AttackerMinSourceDistance"]     = lambda x: x.attacker_min_source_distance()
        d["AttackerReceiveRatio"]          = lambda x: x.attackers_receive_ratio()

        d["NormalLatency"]                 = lambda x: x.average_normal_latency()
        d["MaxNormalLatency"]              = lambda x: x.maximum_normal_latency()
        d["NormalInterArrivalTimeAverage"] = lambda x: x.normal_inter_arrival_time_average()
        d["NormalInterArrivalTimeVar"]     = lambda x: x.normal_inter_arrival_time_variance()
        d["NormalInterArrivalTimes"]       = lambda x: MetricsCommon.smaller_list_str(["{:0.5f}".format(i) for i in x.normal_inter_arrival_time()]).replace("'", "")
        d["NormalInterGenTimeAverage"]     = lambda x: x.normal_inter_generation_time_average()
        d["NormalInterGenTimeVar"]         = lambda x: x.normal_inter_generation_time_variance()
        d["NormalInterGenTimes"]           = lambda x: MetricsCommon.smaller_list_str(["{:0.5f}".format(i) for i in x.normal_inter_generation_time()]).replace("'", "")
        d["NormalSinkSourceHops"]          = lambda x: x.average_sink_source_hops()
        d["NormalSent"]                    = lambda x: x.number_sent("Normal")
        d["UniqueNormalGenerated"]         = lambda x: len(x.normal_sent_time)

        #d["MessageReceiveInterval"]        = lambda x: str(x.message_receive_interval())

        d["NodeWasSource"]                 = lambda x: MetricsCommon.smaller_dict_str(x.node_was_source())
        d["NodeTransitions"]               = lambda x: MetricsCommon.smaller_dict_str(dict(x.node_transitions))

        d["SentHeatMap"]                   = lambda x: MetricsCommon.compressed_dict_str(x.sent_heat_map())
        d["ReceivedHeatMap"]               = lambda x: MetricsCommon.compressed_dict_str(x.received_heat_map())

        d["TimeBinWidth"]                  = lambda x: x._time_bin_width
        d["SentOverTime"]                  = lambda x: MetricsCommon.smaller_dict_str(dict(x.sent_over_time))

        d["ReceivedFromCloserOrSameHops"]  = lambda x: MetricsCommon.smaller_dict_str(x.rcvd_closer_or_same_hops_all())
        d["ReceivedFromFurtherHops"]       = lambda x: MetricsCommon.smaller_dict_str(x.rcvd_further_hops_all())
        d["ReceivedFromCloserOrSameMeters"]= lambda x: MetricsCommon.smaller_dict_str(x.rcvd_closer_or_same_meters_all())
        d["ReceivedFromFurtherMeters"]     = lambda x: MetricsCommon.smaller_dict_str(x.rcvd_further_meters_all())

        d["DeliveredFromCloserOrSameHops"]  = lambda x: MetricsCommon.smaller_dict_str(x.deliv_closer_or_same_hops_all())
        d["DeliveredFromFurtherHops"]       = lambda x: MetricsCommon.smaller_dict_str(x.deliv_further_hops_all())
        d["DeliveredFromCloserOrSameMeters"]= lambda x: MetricsCommon.smaller_dict_str(x.deliv_closer_or_same_meters_all())
        d["DeliveredFromFurtherMeters"]     = lambda x: MetricsCommon.smaller_dict_str(x.deliv_further_meters_all())

        d["FaultsOccured"]                 = lambda x: x.faults_occurred()

        d["DetectedBoots"]                 = lambda x: x.detected_boot_events()
        d["DetectedTotalBoots"]            = lambda x: x.detected_boot_events_total()

        # Link quality metrics
        #d["DeliveredRssi"]                 = lambda x: MetricsCommon.compressed_dict_str(x.delivered_rssi_stats())
        #d["DeliveredLqi"]                  = lambda x: MetricsCommon.compressed_dict_str(x.delivered_lqi_stats())

        d["Errors"]                        = lambda x: MetricsCommon.smaller_dict_str(dict(x.errors))

        return d

    @classmethod
    def print_header(cls, stream=None):
        """Print the results header to the specified stream (defaults to sys.stdout)."""
        print("#" + "|".join(cls.items().keys()), file=stream)

    def get_results(self):
        """Get the results in the result file format."""
        results = []

        for (name, fn) in self.items().items():
            try:
                result = str(fn(self))
            except Exception as ex:
                import traceback
                print("Error finding the value of '{}': {}".format(name, ex), file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
                result = "None"

            results.append(result)

        return "|".join(results)

    def print_results(self, stream=None):
        """Print the results to the specified stream (defaults to sys.stdout)."""
        try:
            print(self.get_results(), file=stream)
        except Exception as ex:
            import traceback
            raise RuntimeError("Failed to get the result string for seed {} (events={}, sim_time={}) caused by {}".format(
                self.seed(), self.event_count, self.sim_time(), traceback.format_exc())
            )

    def print_warnings(self, stream=None):
        """Print any warnings about result consistency."""

        if np.isnan(self.first_normal_sent_time()):
            print("First Normal Sent Time is NaN:", file=stream)
            print("\tMake sure a Normal message is sent.", file=stream)

        if np.isnan(self.receive_ratio()):
            print("Receive Ratio is NaN:", file=stream)
            print("\tMake sure a Normal message is sent.", file=stream)

        if self.reached_sim_upper_bound():
            print("Reached Upper Bound:", file=stream)
            print("\tSimulation reached the upper bound, likely because the safety period was not triggered.", file=stream)
            print("\tEnsure that a Normal message is sent in your simulation.", file=stream)

        if len(self.node_booted_at) != self.sim.configuration.size():
            print("Some node's boot events were missed:", file=stream)
            print("\tMissing:", set(self.sim.configuration.topology.nodes.keys()) - set(self.node_booted_at.keys()))
            print("\tExtra:", set(self.node_booted_at.keys()) - set(self.sim.configuration.topology.nodes.keys()))

        for (nid, events) in self.node_booted_at.items():
            if len(events) > 1:
                print(f"Multiple boot events ({len(events)}) detected for {nid}", file=stream)

    def memory_info(self, attr):
        """Memory usage of the current process in bytes."""
        if psutil is None:
            return None
        else:
            return getattr(psutil.Process().memory_info(), attr)

class AvroraPacketSummary(object):
    __slots__ = ('sent_bytes', 'sent_packets', 'recv_bytes', 'recv_packets', 'corrupted_bytes', 'lost_in_middle_bytes')

    def __init__(self, sent_bytes, sent_packets, recv_bytes, recv_packets, corrupted_bytes, lost_in_middle_bytes):
        self.sent_bytes = sent_bytes
        self.sent_packets = sent_packets
        self.recv_bytes = recv_bytes
        self.recv_packets = recv_packets
        self.corrupted_bytes = corrupted_bytes
        self.lost_in_middle_bytes = lost_in_middle_bytes

class AvroraMetricsCommon(MetricsCommon):
    """Contains metrics specific to the Avrora simulator."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.avrora_sim_cycles = None
        self.avrora_packet_summary = {}
        self.avrora_energy_summary = {}

        # With colours on we can find out the bytes that got corrupted
        # and so work out some of the summary stats on the fly.
        # However, I'm not sure how lost_in_middle bytes are calculated.
        # So for now, lets just ignore these metrics and use the
        # packet summary instead.
        # But the packet summary does not print if we terminate early
        # because the attacker has caught the source.
        self.register('AVRORA-TX', self.process_avrora_tx)
        self.register('AVRORA-RX', self.process_avrora_rx)

        self.register('AVRORA-SIM-CYCLES', self.process_avrora_sim_cycles)
        self.register('AVRORA-PACKET-SUMMARY', self.process_avrora_packet_summary)
        self.register('AVRORA-ENERGY-STATS', self.process_avrora_energy_summary)

    def process_avrora_tx(self, d_or_e, node_id, time, detail):
        radio_bytes, radio_time = detail.split(',')

        radio_bytes = bytearray.fromhex(radio_bytes.replace(".", " "))
        radio_time = float(radio_time)

    def process_avrora_rx(self, d_or_e, node_id, time, detail):
        radio_bytes, radio_time = detail.split(',')

        radio_bytes = bytearray.fromhex(radio_bytes.replace(".", " "))
        radio_time = float(radio_time)

    def process_avrora_sim_cycles(self, d_or_e, node_id, time, detail):
        self.avrora_sim_cycles = int(detail)

    def process_avrora_packet_summary(self, d_or_e, node_id, time, detail):
        summary = AvroraPacketSummary(*tuple(map(int, detail.split(','))))

        ord_node_id, top_node_id = self._process_node_id(node_id)

        self.avrora_packet_summary[top_node_id] = summary

    def process_avrora_energy_summary(self, d_or_e, node_id, time, detail):
        summary = pickle.loads(base64.b64decode(detail))

        ord_node_id, top_node_id = self._process_node_id(node_id)

        self.avrora_energy_summary[top_node_id] = summary

    def total_packet_stat(self, name):
        return sum(getattr(stat, name) for stat in self.avrora_packet_summary.values())

    def total_joules(self):
        return sum(energy.total_joules() for energy in self.avrora_energy_summary.values())

    def total_component_joules(self, component):
        return sum(energy.components[component][0] for energy in self.avrora_energy_summary.values())

    def average_cpu_state(self, state):
        return np.mean([energy.cpu_state_percent(state) for energy in self.avrora_energy_summary.values()])

    def average_cpu_low_power(self):
        return np.mean([energy.cpu_low_power_percent() for energy in self.avrora_energy_summary.values()])

    def average_radio_state(self, state):
        return np.mean([energy.radio_state_percent(state) for energy in self.avrora_energy_summary.values()])

    def average_cpu_state_joules(self, state):
        return np.mean([energy.cpu_state_joules(state) for energy in self.avrora_energy_summary.values()])

    def average_cpu_low_power_joules(self):
        return np.mean([energy.cpu_low_power_joules() for energy in self.avrora_energy_summary.values()])

    def average_radio_state_joules(self, state):
        return np.mean([energy.radio_state_joules(state) for energy in self.avrora_energy_summary.values()])

    @staticmethod
    def items():
        d = OrderedDict()

        d["AvroraSimCycles"]               = lambda x: x.avrora_sim_cycles

        d["TotalJoules"]                   = lambda x: x.total_joules()

        for component in ("CPU", "Yellow", "Green", "Red", "Radio", "SensorBoard", "flash"):
            d[f"Total{component}Joules"] = lambda x, component=component: x.total_component_joules(component)

        # CPU and radio percent
        d["AverageCPUActivePC"]            = lambda x: x.average_cpu_state("Active")
        d["AverageCPUIdlePC"]              = lambda x: x.average_cpu_state("Idle")
        d["AverageCPULowPowerPC"]          = lambda x: x.average_cpu_low_power()

        d["AverageRadioTXPC"]              = lambda x: x.average_radio_state("Transmit (Tx)")
        d["AverageRadioRXPC"]              = lambda x: x.average_radio_state("Receive (Rx)")
        d["AverageRadioPowerIdlePC"]       = lambda x: x.average_radio_state("Idle")
        d["AverageRadioPowerOffPC"]        = lambda x: x.average_radio_state("Power Off")
        d["AverageRadioPowerDownPC"]       = lambda x: x.average_radio_state("Power Down")

        # CPU and radio energy
        d["AverageCPUActiveJoules"]        = lambda x: x.average_cpu_state_joules("Active")
        d["AverageCPUIdleJoules"]          = lambda x: x.average_cpu_state_joules("Idle")
        d["AverageCPULowPowerJoules"]      = lambda x: x.average_cpu_low_power_joules()

        d["AverageRadioTXJoules"]          = lambda x: x.average_radio_state_joules("Transmit (Tx)")
        d["AverageRadioRXJoules"]          = lambda x: x.average_radio_state_joules("Receive (Rx)")
        d["AverageRadioPowerIdleJoules"]   = lambda x: x.average_radio_state_joules("Idle")
        d["AverageRadioPowerOffJoules"]    = lambda x: x.average_radio_state_joules("Power Off")
        d["AverageRadioPowerDownJoules"]   = lambda x: x.average_radio_state_joules("Power Down")

        # Packet Info
        d["TotalSentBytes"]                = lambda x: x.total_packet_stat("sent_bytes")
        d["TotalSentPackets"]              = lambda x: x.total_packet_stat("sent_packets")
        d["TotalRecvBytes"]                = lambda x: x.total_packet_stat("recv_bytes")
        d["TotalRecvPackets"]              = lambda x: x.total_packet_stat("recv_packets")
        d["TotalCorruptedBytes"]           = lambda x: x.total_packet_stat("corrupted_bytes")
        d["TotalLostInMiddleBytes"]        = lambda x: x.total_packet_stat("lost_in_middle_bytes")

        return d

class FakeMetricsCommon(MetricsCommon):
    """Contains fake message techniques specified metrics."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def times_fake_node_changed_to_fake(self):
        total_count = 0

        for ((old_type, new_type), count) in self.node_transitions.items():

            if "FakeNode" in old_type and "FakeNode" in new_type:
                total_count += count

        return total_count

    @staticmethod
    def items(fake_node_types):
        d = OrderedDict()
        
        d["FakeSent"]               = lambda x: x.number_sent("Fake")

        for (fake_short, fake_long) in sorted(fake_node_types.items(), key=lambda x: x[0]):
            d[fake_short]           = lambda x, fake_long=fake_long: x.times_node_changed_to(fake_long)

        d["FakeToNormal"]           = lambda x: x.times_node_changed_to("NormalNode", from_types=fake_node_types.values())
        d["FakeToFake"]             = lambda x: x.times_fake_node_changed_to_fake()
        d["FakeNodesAtEnd"]         = lambda x: x.times_node_changed_to(fake_node_types.values(), from_types="NormalNode") - \
                                                x.times_node_changed_to("NormalNode", from_types=fake_node_types.values())

        d["ReceivedFromCloserOrSameHopsFake"]  = lambda x: MetricsCommon.smaller_dict_str(x.rcvd_closer_or_same_hops("Fake"))
        d["ReceivedFromFurtherHopsFake"]       = lambda x: MetricsCommon.smaller_dict_str(x.rcvd_further_hops("Fake"))
        d["ReceivedFromCloserOrSameMetersFake"]= lambda x: MetricsCommon.smaller_dict_str(x.rcvd_closer_or_same_meters("Fake"))
        d["ReceivedFromFurtherMetersFake"]     = lambda x: MetricsCommon.smaller_dict_str(x.rcvd_further_meters("Fake"))

        return d

class TreeMetricsCommon(MetricsCommon):
    """Contains tree routing specific metrics."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.parent_changes = Counter()
        self.true_parent_changes = Counter()

        self.register('M-PC', self.process_parent_change_event)

    def process_parent_change_event(self, d_or_e, node_id, time, detail):
        (current_parent, new_parent) = detail.split(',')

        current_parent = int(current_parent)

        ord_node_id, top_node_id = self._process_node_id(node_id)

        self.parent_changes[top_node_id] += 1

        if current_parent != AM_BROADCAST_ADDR:
            self.true_parent_changes[top_node_id] += 1

    def total_parent_changes(self):
        return sum(self.parent_changes.values())

    def total_true_parent_changes(self):
        return sum(self.true_parent_changes.values())

    def parent_change_heat_map(self):
        return dict(self.parent_changes)

    def true_parent_change_heat_map(self):
        return dict(self.true_parent_changes)

    @staticmethod
    def items():
        d = OrderedDict()

        d["TotalParentChanges"]            = lambda x: x.total_parent_changes()
        d["TotalTrueParentChanges"]        = lambda x: x.total_true_parent_changes()

        d["ParentChangeHeatMap"]           = lambda x: MetricsCommon.compressed_dict_str(x.true_parent_change_heat_map())

        return d

class RssiMetricsCommon(MetricsCommon):
    """For algorithms that measure the RSSI."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.register('M-RSSI', self.process_rssi_event)

    def process_rssi_event(self, d_or_e, node_id, time, detail):
        (average, smallest, largest, reads, channel) = detail.split(',')

        print(f"RSSI on {node_id} at {time} : {detail}")

    @staticmethod
    def items():
        d = OrderedDict()
        return d


METRIC_GENERIC_DUTY_CYCLE_START = 2013

class DutyCycleMetricsCommon(MetricsCommon):
    """For algorithms that duty cycle the radio."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._duty_cycle_state = {}
        self._duty_cycle_states = defaultdict(list)
        self._duty_cycle = defaultdict(int)
        self._duty_cycle_start = None

        # Duty cycle is indicated by the blue led / led 2
        # When led is on the radio is on and vice verse
        self.register('LedsC', self._process_leds_event)
        self.register('LedsCooja', self._process_leds_cooja_event)

        self.register_generic(METRIC_GENERIC_DUTY_CYCLE_START, self._process_duty_cycle_start)

    def _process_leds_event(self, d_or_e, node_id, time, detail):
        (led, status) = detail.split(',')

        if led == "2":
            self._process_duty_cycle(node_id, time, status == "on")

    def _process_leds_cooja_event(self, d_or_e, node_id, time, detail):
        status = detail.split(",")[2]

        self._process_duty_cycle(node_id, time, status == "1")

    def _process_duty_cycle(self, node_id, time, state):
        ord_node_id, top_node_id = self._process_node_id(node_id)

        (previous_state, previous_time) = self._duty_cycle_state.get(ord_node_id, (None, None))

        # Check if state has changed, if not do nothing
        if previous_state == state:
            return

        time = self.sim_time()

        # We want to catch True to False transitions, once duty cycling has started
        if previous_state is True and state is False and self._duty_cycle_start is not None:
            self._duty_cycle[ord_node_id] += (time - previous_time)

        self._duty_cycle_state[ord_node_id] = (state, time)
        self._duty_cycle_states[ord_node_id].append((state, time))

    def _process_duty_cycle_start(self, d_or_e, node_id, time, data):
        self._duty_cycle_start = self.sim_time()

        for (nid, (previous_state, previous_time)) in self._duty_cycle_state.items():
            self._duty_cycle_state[nid] = (previous_state, self._duty_cycle_start)

    def _calculate_node_duty_cycle(self, node_id):

        # TODO: Calculate start time from the first_normal_sent_time
        # so the duty cycle is only calculated for when the nodes
        # are actually duty cycling.
        #start_time = self.first_normal_sent_time()

        start_time = self._duty_cycle_start
        end_time = self.sim_time()

        # If we never received a duty cycle start event, then assume it starts after boot
        if start_time is None:
            start_time = next(iter(self.node_booted_at[node_id]))

        (state, state_time) = self._duty_cycle_state[node_id]

        duty_time = self._duty_cycle[node_id]

        # If the last transition was to turn the radio on
        # Then we need to count this time up to the end time
        if state is True:
            duty_time += (end_time - state_time)

        return duty_time / (end_time - start_time)

    def duty_cycle(self):
        return {
            nid: round(self._calculate_node_duty_cycle(nid), 5)
            for nid in self._duty_cycle_state.keys()
        }

    @staticmethod
    def items():
        d = OrderedDict()
        d["DutyCycleStart"]                = lambda x: str(x._duty_cycle_start)
        d["DutyCycle"]                     = lambda x: MetricsCommon.smaller_dict_str(x.duty_cycle(), sort=True)
        return d


class DutyCycleMetricsGrapher(MetricsCommon):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def finish(self):
        super().finish()

        if isinstance(self, DutyCycleMetricsCommon):
            self._plot_duty_cycle()

    def _plot_duty_cycle(self):
        import matplotlib.pyplot as plt
        from matplotlib.font_manager import FontProperties

        fig, ax = plt.subplots()

        # From: https://stackoverflow.com/questions/4700614/how-to-put-the-legend-out-of-the-plot
        box = ax.get_position()
        ax.set_position((box.x0, box.y0 + box.height * 0.1, box.width, box.height * 0.9))

        for node_id in self.topology.nodes:
            states = self._duty_cycle_states[node_id]
            states = [(False, 0)] + states + [(states[-1][0], self.sim_time())]

            combined = [(atime, btime) for ((astate, atime), (bstate, btime)) in pairwise(states) if astate]

            ax.hlines(node_id.nid, 0, self.sim_time(), "lightgray", linewidth=4, zorder=1)

            for (start, stop) in combined:
                ax.hlines(node_id.nid, start, stop, "mediumaquamarine", linewidth=4, zorder=2)

        node_ids = [node_id.nid for node_id in self.topology.nodes]
        ymin, ymax = min(node_ids), max(node_ids)
        ymin -= 0.05 * (ymax - ymin)
        ymax += 0.05 * (ymax - ymin)
        ax.set_ylim(bottom=ymin, top=ymax)

        xmin, xmax = 0, self.sim_time()
        xmin -= 0.05 * (ymax - ymin)
        xmax += 0.05 * (ymax - ymin)
        ax.set_xlim(left=xmin, right=xmax)

        font_prop = FontProperties()
        font_prop.set_size("small")

        legend = ax.legend(loc="upper center", bbox_to_anchor=(0.45,-0.15), ncol=6, prop=font_prop)

        ax.set_xlabel("Time (seconds)")
        ax.set_ylabel("Node ID")

        plt.savefig("dutycycle.pdf")

    @staticmethod
    def items():
        d = OrderedDict()
        return d

class MessageTimeMetricsGrapher(MetricsCommon):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.register('M-CB', self.log_time_bcast_event)
        self.register('M-CD', self.log_time_deliver_event)
        self.register('M-NC', self.log_time_node_change_event)

        self._bcasts = defaultdict(list)
        self._delivers = defaultdict(list)
        self._attacker_delivers = {}
        self._attacker_history = defaultdict(list)
        self._node_change = defaultdict(list)


    def log_time_bcast_event(self, d_or_e, node_id, time, detail):
        (kind, status, ultimate_source_id, sequence_number, tx_power, hex_buffer) = detail.split(',')

        # If the BCAST succeeded, then status was SUCCESS (See TinyError.h)
        if status != "0":
            return

        time = float(time)
        kind = self.message_kind_to_string(kind)
        ord_node_id, top_node_id = self._process_node_id(node_id)

        try:
            contents = self.parse_message(kind, hex_buffer)
        except KeyError:
            contents = None


        self._bcasts[kind].append((time, ord_node_id, f"{contents}"))

    def log_time_deliver_event(self, d_or_e, node_id, time, detail):
        try:
            (kind, target, proximate_source_id, ultimate_source_id, sequence_number, rssi, lqi, hex_buffer) = detail.split(',')
        except ValueError:
            (kind, proximate_source_id, ultimate_source_id, sequence_number, rssi, lqi) = detail.split(',')

        time = float(time)
        kind = self.message_kind_to_string(kind)
        ord_node_id, top_node_id = self._process_node_id(node_id)

        try:
            contents = self.parse_message(kind, hex_buffer)
        except KeyError:
            contents = None

        self._delivers[kind].append((time, ord_node_id, f"{contents}"))

    def log_time_node_change_event(self, d_or_e, node_id, time, detail):
        (old_name, new_name) = detail.split(',')

        time = float(time)
        old_name = self.node_kind_to_string(old_name)
        new_name = self.node_kind_to_string(new_name)
        ord_node_id, top_node_id = self._process_node_id(node_id)

        self._node_change[new_name].append((time, ord_node_id, f"{old_name}"))

    def _plot_message_events(self, values, filename, line_values=None, y2label=None, with_dutycycle=False, interactive=False):
        import matplotlib.pyplot as plt
        from matplotlib.font_manager import FontProperties

        if interactive:
            import mpld3

        fig, ax = plt.subplots()

        # From: https://stackoverflow.com/questions/4700614/how-to-put-the-legend-out-of-the-plot
        box = ax.get_position()
        ax.set_position((box.x0, box.y0 + box.height * 0.1, box.width, box.height * 0.9))

        # Plot events
        for (kind, details) in sorted(values.items(), key=lambda x: x[0]):
            xya = [(time, ord_node_id.nid, anno) for (time, ord_node_id, anno) in details]
            xs, ys, annos = zip(*xya)
            scatter = ax.scatter(xs, ys, c=message_type_to_colour(kind), label=kind, s=4, zorder=4, marker="o")

            if interactive:
                tooltip = mpld3.plugins.PointLabelTooltip(scatter, labels=annos)
                mpld3.plugins.connect(fig, tooltip)

        # Plot node changes
        for (kind, details) in sorted(self._node_change.items(), key=lambda x: x[0]):
            xya = [(time, ord_node_id.nid, anno) for (time, ord_node_id, anno) in details]
            xs, ys, annos = zip(*xya)
            scatter = ax.scatter(xs, ys, c=node_type_to_colour(kind), label=kind[:-len("Node")], s=12, zorder=3, marker="s")

            if interactive:
                tooltip = mpld3.plugins.PointLabelTooltip(scatter, labels=annos)
                mpld3.plugins.connect(fig, tooltip)

        if line_values is not None:
            xs, ys = zip(*line_values)

            if y2label is None:
                ax.plot(xs, ys)
            else:
                ax2 = ax.twinx()
                ax2.set_position((box.x0, box.y0 + box.height * 0.1, box.width, box.height * 0.9))

                ax2.plot(xs, ys, zorder=5)

                ax2.set_ylabel(y2label)

                ymin, ymax = 0, max(ys)
                ymin -= 0.05 * (ymax - ymin)
                ymax += 0.05 * (ymax - ymin)
                ax2.set_ylim(bottom=ymin, top=ymax)

        if with_dutycycle:
            for node_id in self.topology.nodes:
                states = self._duty_cycle_states[node_id]
                states = [(False, 0)] + states + [(states[-1][0], self.sim_time())]

                combined = [(atime, btime) for ((astate, atime), (bstate, btime)) in pairwise(states) if astate]

                ax.hlines(node_id.nid, 0, self.sim_time(), "lightgray", linewidth=4, zorder=1)

                for (start, stop) in combined:
                    ax.hlines(node_id.nid, start, stop, "mediumaquamarine", linewidth=4, zorder=2)

        node_ids = [node_id.nid for node_id in self.topology.nodes]
        ymin, ymax = min(node_ids), max(node_ids)
        ymin -= 0.05 * (ymax - ymin)
        ymax += 0.05 * (ymax - ymin)
        ax.set_ylim(bottom=ymin, top=ymax)

        font_prop = FontProperties()
        font_prop.set_size("small")

        legend = ax.legend(loc="upper center", bbox_to_anchor=(0.45,-0.15), ncol=6, prop=font_prop)

        ax.set_xlabel("Time (seconds)")
        ax.set_ylabel("Node ID")

        if interactive:
            mpld3.show()

        plt.savefig(filename)

    def finish(self):
        super().finish()

        self._plot_message_events(self._bcasts, "bcasts.pdf")#, interactive=True)
        self._plot_message_events(self._delivers, "delivers.pdf")

        if isinstance(self, DutyCycleMetricsCommon):
            self._plot_message_events(self._bcasts, "bcasts_duty.pdf", with_dutycycle=True)
            self._plot_message_events(self._delivers, "delivers_duty.pdf", with_dutycycle=True)

        for (attacker_id, values) in self._attacker_delivers.items():
            line_values = [(time, node_id.nid) for (time, node_id) in self._attacker_history[attacker_id]]
            values = {k: [detail + (None,) for detail in details] for (k, details) in values.items()}
            self._plot_message_events(values, f"attacker{attacker_id}_delivers_nid.pdf", line_values=line_values)

        for source_id in self.configuration.source_ids:
            for (attacker_id, values) in self._attacker_delivers.items():
                line_values = [
                    (time, self.configuration.node_source_distance_meters(node_id, source_id))
                    for (time, node_id)
                    in self._attacker_history[attacker_id]
                ]
                values = {k: [detail + (None,) for detail in details] for (k, details) in values.items()}
                self._plot_message_events(values, f"attacker{attacker_id}_delivers_dsrcm{source_id}.pdf",
                           line_values=line_values, y2label=f"Source {source_id} Distance (meters)")

    @staticmethod
    def items():
        d = OrderedDict()
        return d

class MessageDutyCycleBoundaryHistogram(MetricsCommon):
    """Generates a histogram of how far off the wakeup period
    a message was received. This extra metric is very focused at
    the adaptive_spr_notify algorithm when used with the
    SLPDutyCycleP duty cycle."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.register('M-CR', self.log_time_receive_event_hist)
        self.register('M-G', self.log_time_generic_event_lpl_on)

        self._delivers_hist = defaultdict(list)
        self._radio_on_times = defaultdict(list)

    def log_time_receive_event_hist(self, d_or_e, node_id, time, detail):
        (kind, proximate_source_id, ultimate_source_id, sequence_number, hop_count) = detail.split(',')

        time = float(time)
        kind = self.message_kind_to_string(kind)
        ord_node_id, top_node_id = self._process_node_id(node_id)

        self._delivers_hist[(kind, ord_node_id)].append(time)

    def log_time_generic_event_lpl_on(self, d_or_e, node_id, time, detail):
        (code, message) = detail.split(",")

        time = float(time)
        ord_node_id, top_node_id = self._process_node_id(node_id)
        code = int(code)

        code_to_name = {
            3001: "Normal",
            3002: "Fake",
            3003: "Choose",
        }

        try:
            code_name = code_to_name[code]

            self._radio_on_times[(code_name, ord_node_id)].append(time)
        except KeyError:
            pass

    def finish(self):
        super().finish()

        message_types = {kind for (kind, ord_node_id) in self._delivers_hist} & {kind for (kind, ord_node_id) in self._radio_on_times}

        for message_type in message_types:
            self._plot_message_duty_cycle_boundary_histogram(message_type)

    def _plot_message_duty_cycle_boundary_histogram(self, message_name):
        import matplotlib.pyplot as plt
        from matplotlib.font_manager import FontProperties

        intervals = {
            "Fake": (100, 150),
            "Choose": (25, 25),
            "Normal": (50, 50),
        }

        early_wakeup_ms, max_wakeup_ms = intervals.get(message_name, (0, 0))

        fig, ax = plt.subplots()

        hist_values = []

        for (node_id, states) in self._duty_cycle_states.items():
            singles = self._radio_on_times[(message_name, node_id)] + [self.sim_time()]

            rcvd_times = self._delivers_hist[(message_name, node_id)]

            for rcvd_time in rcvd_times:
                possible = [start1 for (start1, start2) in pairwise(singles) if start1 <= rcvd_time < start2]

                if len(possible) == 1:
                    start = possible[0]

                    hist_time = (rcvd_time - start) * 1000 - early_wakeup_ms

                    hist_values.append(hist_time)
                else:
                    if len(possible) > 0:
                        print(f"Multiple times {possible} for {rcvd_time} for msg {message_name} on {node_id}")

        if len(hist_values) > 0:
            bins = int(math.ceil(max(hist_values)-min(hist_values))/5)
            try:
                ax.hist(hist_values, bins=bins, color=message_type_to_colour(message_name))
            except ValueError as ex:
                print(ex)
                ax.hist(hist_values, bins="auto", color=message_type_to_colour(message_name))

            ax.set_xlabel("Difference (ms)")
            ax.set_ylabel("Count")

            plt.savefig(f"{message_name}dutycycleboundaryhist.pdf")


EXTRA_METRICS = (DutyCycleMetricsGrapher, MessageTimeMetricsGrapher, MessageDutyCycleBoundaryHistogram)
EXTRA_METRICS_CHOICES = [cls.__name__ for cls in EXTRA_METRICS]

def import_algorithm_metrics(module_name, sim, extra_metrics=None):
    """Get the class to be used to gather metrics on the simulation.
    This will mixin metric gathering for certain simulator tools if necessary.
    If not, the regular metrics class will be provided."""
    import importlib

    simulator_to_mixin = {
        "avrora": AvroraMetricsCommon,
    }

    extra_metrics = [] if extra_metrics is None else [cls for cls in EXTRA_METRICS if cls.__name__ in extra_metrics]

    mixin_class = simulator_to_mixin.get(sim, None)

    algo_module = importlib.import_module(f"{module_name}.Metrics")

    if mixin_class is None and len(extra_metrics) == 0:
        return algo_module.Metrics

    super_classes = ([] if mixin_class is None else [mixin_class]) + extra_metrics

    class MixinMetrics(algo_module.Metrics, *super_classes):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        @staticmethod
        def items():
            d = algo_module.Metrics.items()
            for cls in super_classes:
                d.update(cls.items())
            return d

    return MixinMetrics
