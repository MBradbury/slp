from __future__ import print_function, division

from collections import namedtuple
import importlib
from itertools import islice
import os
import random
import sys
import timeit

import numpy as np

import simulator.CommunicationModel

Node = namedtuple('Node', ('nid', 'location', 'tossim_node'), verbose=False)

class Simulation(object):
    def __init__(self, module_name, configuration, args, load_nesc_variables=False):

        tossim_module = importlib.import_module('{}.TOSSIM'.format(module_name))

        if load_nesc_variables:
            from tinyos.tossim.TossimApp import NescApp

            app_path = os.path.join('.', module_name.replace('.', os.sep), 'app.xml')

            self.nesc_app = NescApp(xmlFile=app_path)
            self.tossim = tossim_module.Tossim(self.nesc_app.variables.variables())

        else:
            self.nesc_app = None
            self.tossim = tossim_module.Tossim([])

        self.radio = self.tossim.radio()

        # Record the seed we are using
        self.seed = args.seed

        # Set tossim seed
        self.tossim.randomSeed(self.seed)

        # Make sure the time starts at 0
        self.tossim.setTime(0)

        self.rng = random.Random(self.seed)

        self.communication_model = args.communication_model
        self.noise_model = args.noise_model
        self.wireless_range = args.distance
        self.latest_node_start_time = args.latest_node_start_time

        # Cache the number of ticks per second.
        # This value should not change throughout the simulation's execution
        self._ticks_per_second = self.tossim.ticksPerSecond()

        self.nodes = []

        self._create_nodes(configuration.topology)

        if hasattr(args, "safety_period"):
            self.safety_period = args.safety_period
        else:
            # To make simulations safer an upper bound on the simulation time
            # is used when no safety period makes sense. This upper bound is the
            # time it would have otherwise taken the attacker to scan the whole network.
            self.safety_period = len(configuration.topology.nodes) * 2.0 * args.source_period.slowest()

        self.safety_period_value = float('inf') if self.safety_period is None else self.safety_period

        if args.mode == "GUI" or args.verbose:
            self.tossim.addChannel("stdout", sys.stdout)
            self.tossim.addChannel("stderr", sys.stderr)
            self.tossim.addChannel("slp-debug", sys.stdout)


        self.attackers = []

        metrics_module = importlib.import_module('{}.Metrics'.format(module_name))

        self.metrics = metrics_module.Metrics(self, configuration)

        self.start_time = None
        self.enter_start_time = None

        self.attacker_found_source = False

    def __enter__(self):

        self.enter_start_time = timeit.default_timer()

        return self

    def __exit__(self, tp, value, tb):

        # Turn off to allow subsequent simulations
        for node in self.nodes:
            node.tossim_node.turnOff()

        del self.nodes
        del self.radio
        del self.tossim

    def register_output_handler(self, name, function):
        """Registers this class to catch the output from the simulation on the given channel."""

        def process_one_line(line):
            (d_or_e, node_id, time, detail) = line.split(':', 3)
            
            # Do not pass newline in detail onwards
            function(d_or_e, node_id, time, detail[:-1])

        self.tossim.addCallback(name, process_one_line)

    def node_distance_meters(self, left, right):
        """Get the euclidean distance between two nodes specified by their ids"""
        return self.metrics.configuration.node_distance_meters(left, right)

    def sim_time(self):
        """Returns the current simulation time in seconds"""
        return self.tossim.timeInSeconds()

    def register_event_callback(self, callback, call_at_time):
        self.tossim.register_event_callback(callback, call_at_time)

    def _create_nodes(self, topology):
        """Creates nodes and initialize their boot times"""
        for (ordered_nid, loc) in topology.nodes.items():
            tossim_node = self.tossim.getNode(ordered_nid)

            tossim_node.setTag(topology.to_topo_nid(ordered_nid))

            self.nodes.append(Node(ordered_nid, loc, tossim_node))

            self.set_boot_time(tossim_node)

    def node_from_ordered_nid(self, ordered_nid):
        for node in self.nodes:
            if node.nid == ordered_nid:
                return node

        raise RuntimeError("Unable to find a node with ordered_nid of {}".format(ordered_nid))

    def node_from_topology_nid(self, topology_nid):

        ordered_nid = self.metrics.configuration.topology.to_ordered_nid(topology_nid)

        for node in self.nodes:
            if node.nid == ordered_nid:
                return node

        raise RuntimeError("Unable to find a node with topology_nid of {}".format(topology_nid))

    def _pre_run(self):
        """Called before the simulator run loop starts"""
        self.setup_radio()
        self.setup_noise_models()

        self.start_time = timeit.default_timer()

    def _post_run(self, event_count):
        """Called after the simulator run loop finishes"""

        current_time = timeit.default_timer()

        # Set the number of seconds this simulation run took.
        # It is possible that we will reach here without setting
        # start_time, so we need to look out for this.

        try:
            self.metrics.total_wall_time = current_time - self.enter_start_time
        except TypeError:
            self.metrics.total_wall_time = None

        try:
            self.metrics.wall_time = current_time - self.start_time
        except TypeError:
            self.metrics.wall_time = None

        self.metrics.event_count = event_count

    def continue_predicate(self):
        """Specifies if the simulator run loop should continue executing."""
        # For performance reasons do not do anything expensive in this function,
        # that includes simple things such as iterating or calling functions.
        return not self.attacker_found_source

    def run(self):
        """Run the simulator loop."""
        event_count = 0
        try:
            self._pre_run()

            if hasattr(self, "_during_run"):
                event_count = self.tossim.runAllEventsWithMaxTimeAndCallback(
                    self.safety_period_value, self.continue_predicate, self._during_run)
            else:
                event_count = self.tossim.runAllEventsWithMaxTime(
                    self.safety_period_value, self.continue_predicate)

        finally:
            self._post_run(event_count)

    def set_boot_time(self, tossim_node):
        """
        Sets the boot time of the given node to be at a
        random time between 0 and self.latest_node_start_time seconds.
        """
        start_time = int(self.rng.uniform(0.0, self.latest_node_start_time) * self._ticks_per_second)
        tossim_node.bootAtTime(start_time)

    def setup_radio(self):
        """Creates radio links for node pairs that are in range."""
        model = simulator.CommunicationModel.eval_input(self.communication_model)

        cm = model()
        cm.setup(self)

        index_to_ordered = self.metrics.configuration.topology.index_to_ordered

        for ((i, j), gain) in np.ndenumerate(cm.link_gain):
            if i == j:
                continue
            if np.isnan(gain):
                continue

            # Convert from the indexes to the ordered node ids
            nidi = index_to_ordered(i)
            nidj = index_to_ordered(j)

            self.radio.add(nidi, nidj, gain)

        for (i, noise_floor) in enumerate(cm.noise_floor):
            nidi = index_to_ordered(i)

            self.radio.setNoise(nidi, noise_floor, cm.white_gausian_noise)

    def setup_noise_models(self):
        """Create the noise model for each of the nodes in the network."""
        path = self.noise_model_path()

        # Instead of reading in all the noise data, a limited amount
        # is used. If we were to use it all it leads to large slowdowns.
        count = 2500

        noises = list(islice(self._read_noise_from_file(path), count))

        for node in self.nodes:
            tnode = node.tossim_node

            tnode.addNoiseTraces(noises)

            tnode.createNoiseModel()

    @staticmethod
    def _read_noise_from_file(path):
        with open(path, "r") as f:
            for line in f:
                if len(line) > 0 and not line.isspace():
                    yield int(line)

    def add_attacker(self, attacker):
        self.attackers.append(attacker)

    def any_attacker_found_source(self):
        return self.attacker_found_source

    def noise_model_path(self):
        """The path to the noise model, specified in the algorithm arguments."""
        return os.path.join('models', 'noise', self.noise_model + '.txt')

    @staticmethod
    def available_noise_models():
        """Gets the names of the noise models available in the noise directory"""
        return ("casino-lab", "meyer-heavy", "ttx4-demo")

        # Querying the files is the best approach. But it is expensive, so lets disable it.
        #import glob
        #return [
        #    os.path.splitext(os.path.basename(noise_file))[0]
        #    for noise_file
        #    in glob.glob('models/noise/*.txt')
        #]

    @staticmethod
    def available_communication_models():
        """Gets the names of the communication models available"""
        return simulator.CommunicationModel.MODEL_NAME_MAPPING.keys()



from datetime import datetime
import heapq
import re

class OfflineSimulation(object):
    def __init__(self, module_name, configuration, args, log_filename):

        # Record the seed we are using
        self.seed = args.seed

        self.rng = random.Random(self.seed)

        self.nodes = []

        self._create_nodes(configuration.topology.nodes)

        if hasattr(args, "safety_period"):
            self.safety_period = args.safety_period
            
        elif hasattr(args, "source_period"):
            # To make simulations safer an upper bound on the simulation time
            # is used when no safety period makes sense. This upper bound is the
            # time it would have otherwise taken the attacker to scan the whole network.
            self.safety_period = len(configuration.topology.nodes) * 2.0 * args.source_period.slowest()

        else:
            self.safety_period = None

        self.safety_period_value = float('inf') if self.safety_period is None else self.safety_period

        self._line_handlers = {}

        self._callbacks = []

        self.attackers = []

        metrics_module = importlib.import_module('{}.Metrics'.format(module_name))

        self.metrics = metrics_module.Metrics(self, configuration)

        # Record the current user's time this script started executing at
        self.start_time = None

        # The times that the actual execution started and ended.
        # They are used to emulate sim_time and calculate the execution length.
        self._real_start_time = None
        self._real_end_time = None

        self.attacker_found_source = False

        self._log_file = open(log_filename, 'r')

    def __enter__(self):
        return self

    def __exit__(self, tp, value, tb):
        self._log_file.close()

    def register_output_handler(self, name, function):
        self._line_handlers[name] = function

    def node_distance_meters(self, left, right):
        """Get the euclidean distance between two nodes specified by their ids"""
        return self.metrics.configuration.node_distance_meters(left, right)

    def sim_time(self):
        """Returns the current simulation time in seconds"""
        return (self._real_end_time - self._real_start_time).total_seconds()

    def register_event_callback(self, callback, call_at_time):
        heapq.heappush(self._callbacks, (call_at_time, callback))

    def _create_nodes(self, node_locations):
        """Creates nodes"""

        for (nid, loc) in node_locations.items():
            self.nodes.append(Node(nid, loc, None))

    def node_from_ordered_nid(self, ordered_nid):
        for node in self.nodes:
            if node.nid == ordered_nid:
                return node

        raise RuntimeError("Unable to find a node with ordered_nid of {}".format(ordered_nid))

    def node_from_topology_nid(self, topology_nid):

        ordered_nid = self.metrics.configuration.topology.to_ordered_nid(topology_nid)

        for node in self.nodes:
            if node.nid == ordered_nid:
                return node

        raise RuntimeError("Unable to find a node with topology_nid of {}".format(topology_nid))

    def _pre_run(self):
        """Called before the simulator run loop starts"""
        self.start_time = timeit.default_timer()

    def _post_run(self, event_count):
        """Called after the simulator run loop finishes"""

        # Set the number of seconds this simulation run took.
        # It is possible that we will reach here without setting
        # start_time, so we need to look out for this.
        try:
            self.metrics.wall_time = timeit.default_timer() - self.start_time
        except TypeError:
            self.metrics.wall_time = None

        self.metrics.event_count = event_count

    def continue_predicate(self):
        """Specifies if the simulator run loop should continue executing."""
        # For performance reasons do not do anything expensive in this function,
        # that includes simple things such as iterating or calling functions.
        return not self.attacker_found_source

    LINE_RE = re.compile(r'([a-zA-Z-]+):([DE]):(\d+):(\d+):(.+)')

    def _parse_line(self, line):

        # Example line:
        #2016/07/27 14:47:34.418:Metric-COMM:22022:D:4:DELIVER:Normal,22022,4,1,1,22

        date_string, rest = line[0: len("2016/07/27 15:09:53.687")], line[len("2016/07/27 15:09:53.687")+1:]

        current_time = datetime.strptime(date_string, "%Y/%m/%d %H:%M:%S.%f")

        match = self.LINE_RE.match(rest)
        if match is not None:
            kind = match.group(1)
            log_type = match.group(2)
            node_id = int(match.group(3))
            node_local_time = int(match.group(4))
            message_line = match.group(5)

            return (current_time, kind, node_local_time, log_type, node_id, message_line)

        else:
            return None

    def run(self):
        """Run the simulator loop."""
        event_count = 0
        try:
            self._pre_run()

            for line in self._log_file:

                result = self._parse_line(line)

                if result is None:
                    print("Warning unable to parse: '{}'. Skipping that line.".format(line), file=sys.stderr)
                    continue

                (current_time, kind, node_local_time, log_type, node_id, message_line) = result

                # Record the start and stop time
                if self._real_start_time is None:
                    self._real_start_time = current_time

                self._real_end_time = current_time

                # Run any callbacks that happened before now
                while True:
                    if len(self._callbacks) == 0:
                        break

                    (call_at_time, callback) = self._callbacks[0]

                    if call_at_time >= self.sim_time():
                        break

                    heapq.heappop(self._callbacks)

                    callback(call_at_time)

                # Stop the run if the attacker has found the source
                if not self.continue_predicate():
                    break

                # Stop if the safety period has expired
                if (self._real_end_time - self._real_start_time).total_seconds() >= self.safety_period_value:
                    break

                # Handle the event
                if kind in self._line_handlers:
                    self._line_handlers[kind](log_type, node_id, self.sim_time(), message_line)

                event_count += 1 

        finally:
            self._post_run(event_count)


    def add_attacker(self, attacker):
        self.attackers.append(attacker)

    def any_attacker_found_source(self):
        return self.attacker_found_source
