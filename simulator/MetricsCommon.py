from __future__ import print_function, division

from collections import Counter, OrderedDict, defaultdict
import base64
import math
import pickle
import sys
import zlib

# Allow missing psutil
try:
    import psutil
except ImportError:
    psutil = None

try:
    # Python 2
    from itertools import izip_longest
except ImportError:
    # Python 3
    from itertools import zip_longest as izip_longest

from itertools import tee

import numpy as np

import simulator.Attacker

# From: https://docs.python.org/3/library/itertools.html#recipes
def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = tee(iterable, 2)
    next(b, None)
    return zip(a, b)

class MetricsCommon(object):
    def __init__(self, sim, configuration):
        self.sim = sim
        self.configuration = configuration
        self.topology = configuration.topology

        self.source_ids = set() # set(configuration.source_ids)
        self.sink_ids = set() # {configuration.sink_id}

        self.sent = defaultdict(Counter)
        self.received = defaultdict(Counter)
        self.delivered = defaultdict(Counter)

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

        self.total_wall_time = None
        self.wall_time = None
        self.event_count = None

        self.errors = Counter()

        self.became_source_times = defaultdict(list)
        self.became_normal_after_source_times = defaultdict(list)

        self.node_transitions = defaultdict(int)

        self.node_types = {}
        self.message_types = {}

        self.register('M-NC', self.process_node_change_event)

        self.register('M-NTA', self.process_node_type_add)
        self.register('M-MTA', self.process_message_type_add)

        # BCAST / RCV / DELIVER events
        self.register('M-CB', self.process_bcast_event)
        self.register('M-CR', self.process_rcv_event)
        self.register('M-CD', self.process_deliver_event)

        self.register('stderr', self.process_error_event)

    def _process_node_id(self, ordered_node_id):
        ordered_node_id = int(ordered_node_id)
        return ordered_node_id, self.topology.to_topo_nid(ordered_node_id)

    def register(self, name, function):
        self.sim.register_output_handler(name, function)

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


    def process_node_type_add(self, d_or_e, node_id, time, detail):
        (ident, name) = detail.split(',')
        self.node_types[int(ident)] = name

    def process_message_type_add(self, d_or_e, node_id, time, detail):
        (ident, name) = detail.split(',')
        self.message_types[int(ident)] = name

    def process_bcast_event(self, d_or_e, node_id, time, detail):
        (kind, status, sequence_number, tx_power) = detail.split(',')

        # If the BCAST succeeded, then status was SUCCESS (See TinyError.h)
        if status != "0":
            return

        ord_node_id, top_node_id = self._process_node_id(node_id)
        time = float(time)

        kind = self.message_kind_to_string(kind)

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

                # Handle starting the duration timeout in the simulation running
                self.sim.trigger_duration_run_start(time)

    def _record_direction_received(self, kind, ord_node_id, proximate_source_id,
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

        ord_proximate_source_id = int(proximate_source_id)

        conf = self.configuration
        topo = conf.topology

        oi = topo.ordered_index
        ttn = topo.to_topo_nid

        idx_proximate_source_id = oi(ord_proximate_source_id)
        idx_node_id = oi(ord_node_id)

        nd = conf._dist_matrix
        ndm = conf._dist_matrix_meters

        for ord_source_id in self.source_ids:
            top_source_id = ttn(ord_source_id)
            idx_source_id = oi(ord_source_id)

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

        kind = self.message_kind_to_string(kind)

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
            self.normal_receive_time[key] = time
            self.normal_hop_count.append(hop_count)

        self._record_direction_received(kind, ord_node_id, proximate_source_id,
                                        self.received_from_further_hops, self.received_from_closer_or_same_hops,
                                        self.received_from_further_meters, self.received_from_closer_or_same_meters)

    def process_deliver_event(self, d_or_e, node_id, time, detail):
        (kind, proximate_source_id, ultimate_source_id, sequence_number, rssi, lqi) = detail.split(',')

        ord_node_id, top_node_id = self._process_node_id(node_id)

        kind = self.message_kind_to_string(kind)

        self.delivered[kind][top_node_id] += 1

        self._record_direction_received(kind, ord_node_id, proximate_source_id,
                                        self.delivered_from_further_hops, self.delivered_from_closer_or_same_hops,
                                        self.delivered_from_further_meters, self.delivered_from_closer_or_same_meters)

    def process_node_change_event(self, d_or_e, node_id, time, detail):
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
        # It is possible that the sink has received no Normal messages
        if len(self.normal_latency) != 0:
            return np.mean(np.fromiter(iter(self.normal_latency.values()), dtype=float))
        else:
            return float('inf')

    def maximum_normal_latency(self):
        if len(self.normal_latency) != 0:
            return max(self.normal_latency.values())
        else:
            return float('inf')

    def minimum_normal_latency(self):
        if len(self.normal_latency) != 0:
            return min(self.normal_latency.values())
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
            raise RuntimeError("We received a message that was not set (sent: {}) (received {})!".format(
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
        ttn = self.topology.to_topo_nid
        ndm = self.configuration.node_distance_meters

        return {
            (ttn(ord_source_id), attacker.ident): ndm(ord_source_id, attacker.position)

            for attacker
            in self.sim.attackers

            for ord_source_id
            in self.source_ids
        }

    def attacker_sink_distance(self):
        ttn = self.topology.to_topo_nid
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
        ttn = self.topology.to_topo_nid

        return {
            (ttn(ord_source_id), attacker.ident): attacker.steps_towards[ord_source_id]

            for attacker
            in self.sim.attackers

            for ord_source_id
            in self.source_ids
        }

    def attacker_steps_away(self):
        ttn = self.topology.to_topo_nid

        return {
            (ttn(ord_source_id), attacker.ident): attacker.steps_away[ord_source_id]

            for attacker
            in self.sim.attackers

            for ord_source_id
            in self.source_ids
        }

    def attacker_min_source_distance(self):
        ttn = self.topology.to_topo_nid

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


    @staticmethod
    def smaller_dict_str(dict_result):
        return str(dict_result).replace(": ", ":").replace(", ", ",")

    @staticmethod
    def compressed_dict_str(dict_result):
        dict_result_bytes = MetricsCommon.smaller_dict_str(dict_result).encode("utf-8")
        return base64.b64encode(zlib.compress(dict_result_bytes, 9))

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
    def __init__(self, sim, configuration):
        super(AvroraMetricsCommon, self).__init__(sim, configuration)

        self.avrora_sim_cycles = None
        self.avrora_packet_summary = {}
        self.avrora_energy_summary = {}

        # With colours on we can find out the bytes that got corrupted
        # and so work out some of the summary stats on the fly.
        # However, I'm not sure how lost_in_middle bytes are calculated.
        # So for now, lets just ignore these metrics and use the
        # packet summary instead
        #self.register('AVRORA-TX', self.process_avrora_tx)
        #self.register('AVRORA-RX', self.process_avrora_rx)

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

        for component in ["CPU", "Yellow", "Green", "Red", "Radio", "SensorBoard", "flash"]:
            d["Total{}Joules".format(component)] = lambda x, component=component: x.total_component_joules(component)

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
    def __init__(self, sim, configuration):
        super(FakeMetricsCommon, self).__init__(sim, configuration)

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

        for (short, long) in sorted(fake_node_types.items(), key=lambda x: x[0]):
            d[short]                    = lambda x: x.times_node_changed_to(long)

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
    def __init__(self, sim, configuration):
        super(TreeMetricsCommon, self).__init__(sim, configuration)

        self.parent_changes = Counter()
        self.true_parent_changes = Counter()

        self.register('M-PC', self.process_parent_change_event)

    def process_parent_change_event(self, d_or_e, node_id, time, detail):
        (current_parent, new_parent) = detail.split(',')

        current_parent = int(current_parent)

        ord_node_id, top_node_id = self._process_node_id(node_id)

        self.parent_changes[top_node_id] += 1

        # 65535 is AM_BROADCAST_ADDR
        if current_parent != 65535:
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
    def __init__(self, sim, configuration):
        super(RssiMetricsCommon, self).__init__(sim, configuration)

        self.register('M-RSSI', self.process_rssi_event)

    def process_rssi_event(self, d_or_e, node_id, time, detail):
        (average, smallest, largest, reads, channel) = detail.split(',')

        print("RSSI on {} at {} : {}".format(node_id, time, detail))

    @staticmethod
    def items():
        d = OrderedDict()

        return d


def import_algorithm_metrics(module_name, simulator):
    """Get the class to be used to gather metrics on the simulation.
    This will mixin metric gathering for certain simulator tools if necessary.
    If not, the regular metrics class will be provided."""
    import importlib

    simulator_to_mixin = {
        "avrora": AvroraMetricsCommon,
    }

    mixin_class = simulator_to_mixin.get(simulator, None)

    algo_module = importlib.import_module("{}.Metrics".format(module_name))

    if mixin_class is None:
        return algo_module.Metrics

    class Metrics(algo_module.Metrics, mixin_class):
        def __init__(self, sim, configuration):
            super(Metrics, self).__init__(sim, configuration)

        @staticmethod
        def items():
            d = algo_module.Metrics.items()
            d.update(mixin_class.items())
            return d

    return Metrics
