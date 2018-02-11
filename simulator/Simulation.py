
import ast
from datetime import datetime
import heapq
import importlib
import os
import random
import sys
import timeit

import numpy as np

import simulator.CommunicationModel as CommunicationModel
import simulator.MetricsCommon as MetricsCommon
import simulator.NoiseModel as NoiseModel

class Node(object):
    __slots__ = ('nid', 'location', 'tossim_node')

    def __init__(self, nid, location, tossim_node):
        self.nid = nid
        self.location = location
        self.tossim_node = tossim_node

class Simulation(object):
    def __init__(self, module_name, configuration, args, load_nesc_variables=False):
        self.module_name = module_name
        self.args = args

        tossim_module = importlib.import_module(f'{module_name}.TOSSIM')

        if load_nesc_variables or args.fault_model.requires_nesc_variables:
            from tinyos.tossim.TossimApp import NescApp

            app_path = os.path.join('.', module_name.replace('.', os.sep), 'app.xml')

            self.nesc_app = NescApp(xmlFile=app_path)
            variables = self.nesc_app.variables.variables()
            self.tossim = tossim_module.Tossim(variables)

        else:
            self.nesc_app = None

            # Don't free C memory allocated at the end, as the OS will
            # do this for us when the process terminates.
            #
            # If we ever get to the point where subsequent runs work well
            # then freeing the memory will be necessary.
            self.tossim = tossim_module.Tossim(should_free=False)

        self.radio = self.tossim.radio()

        # Record the seed we are using
        self.seed = args.seed

        # Set tossim seed
        self.tossim.randomSeed(self.seed)

        # Make sure the time starts at 0
        self.tossim.setTime(0)

        self.rng = random.Random(self.seed)

        self.configuration = configuration
        self.communication_model = args.communication_model
        self.noise_model = args.noise_model
        self.wireless_range = args.distance
        self.latest_node_start_time = args.latest_node_start_time

        # Cache the number of ticks per second.
        # This value should not change throughout the simulation's execution
        self._ticks_per_second = self.tossim.ticksPerSecond()

        self.nodes = []

        self._create_nodes(configuration.topology)

        slowest_source_period = args.source_period if isinstance(args.source_period, float) else args.source_period.slowest()
        self.upper_bound_safety_period = configuration.size() * 4.0 * slowest_source_period

        # To make simulations safer an upper bound on the simulation time
        # is used when no safety period makes sense. This upper bound is the
        # time it would have otherwise taken the attacker to scan the whole network.
        self.safety_period = getattr(args, "safety_period", self.upper_bound_safety_period)

        self.safety_factor = getattr(args, "safety_factor", 1.0)

        self.safety_period_value = float('inf') if self.safety_period is None else (self.safety_period * self.safety_factor)

        if args.mode == "GUI" or args.verbose:
            self.tossim.addChannel("stdout", sys.stdout)
            self.tossim.addChannel("stderr", sys.stderr)

        self.fault_model = args.fault_model

        self.attackers = []

        metrics_class = MetricsCommon.import_algorithm_metrics(module_name, args.sim, args.extra_metrics)

        self.metrics = metrics_class(self, configuration)

        self.start_time = None
        self.enter_start_time = None
        self._duration_start_time = None

        self.attacker_found_source = False

    def __enter__(self):

        self.fault_model.setup(self)

        self.enter_start_time = timeit.default_timer()

        return self

    def __exit__(self, tp, value, tb):

        self.metrics.finish()

        # Turn off to allow subsequent simulations
        for node in self.nodes:
            node.tossim_node.turnOff()

        del self.nodes
        del self.radio
        del self.tossim

    def register_output_handler(self, name, function):
        """Registers this class to catch the output from the simulation on the given channel."""

        if function is not None:
            def process_one_line(line):
                # Do not pass newline in detail onwards
                args = line[:-1].split(':', 3)
                
                # Checking that event time and sim time correspond
                #(d_or_e, node_id, time, detail) = args
                #time = float(time)
                #rounded_sim_time = round(self.sim_time(), 6)
                #if time != rounded_sim_time:
                #    print(f"Event occurred at {time} and sim_time of {rounded_sim_time}")

                function(*args)

            self.tossim.addCallback(name, process_one_line)

    def node_distance_meters(self, left, right):
        """Get the euclidean distance between two nodes specified by their ids"""
        return self.configuration.node_distance_meters(left, right)

    def sim_time(self):
        """Returns the current simulation time in seconds"""
        return self.tossim.timeInSeconds()

    def register_event_callback(self, callback, call_at_time):
        self.tossim.register_event_callback(callback, call_at_time)

    def _create_nodes(self, topology):
        """Creates nodes and initialize their boot times"""
        for (ordered_nid, loc) in topology.nodes.items():
            tossim_node = self.tossim.getNode(ordered_nid.nid)

            tossim_node.setTag(topology.o2t(ordered_nid).nid)

            self.nodes.append(Node(ordered_nid, loc, tossim_node))

            self.set_boot_time(tossim_node)

    def node_from_ordered_nid(self, ordered_nid):
        for node in self.nodes:
            if node.nid == ordered_nid:
                return node

        raise RuntimeError(f"Unable to find a node with ordered_nid of {ordered_nid}")

    def node_from_topology_nid(self, topology_nid):
        ordered_nid = self.configuration.topology.t2o(topology_nid)

        for node in self.nodes:
            if node.nid == ordered_nid:
                return node

        raise RuntimeError(f"Unable to find a node with topology_nid of {topology_nid}")

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

    def trigger_duration_run_start(self, time):
        if self._duration_start_time is None:
            self._duration_start_time = time
        self.tossim.triggerRunDurationStart()

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
                event_count = self.tossim.runAllEventsWithTriggeredMaxTimeAndCallback(
                    self.safety_period_value, self.upper_bound_safety_period, self.continue_predicate, self._during_run)
            else:
                event_count = self.tossim.runAllEventsWithTriggeredMaxTime(
                    self.safety_period_value, self.upper_bound_safety_period, self.continue_predicate)

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
        cm = CommunicationModel.eval_input(self.communication_model)
        cm.setup(self)

        ri2o = self.configuration.topology.ri2o
        isnan = np.isnan

        wgn = cm.white_gausian_noise

        radio_add = self.radio.add
        radio_setNoise = self.radio.setNoise

        for ((i, j), gain) in np.ndenumerate(cm.link_gain):
            if i == j:
                continue
            if isnan(gain):
                continue

            # Convert from the indexes to the ordered node ids
            nidi = ri2o(i).nid
            nidj = ri2o(j).nid

            radio_add(nidi, nidj, gain)

        for (i, noise_floor) in enumerate(cm.noise_floor):
            nidi = ri2o(i).nid

            radio_setNoise(nidi, noise_floor, wgn)

    def setup_noise_models(self):
        """Create the noise model for each of the nodes in the network."""
        nm = NoiseModel.eval_input(self.noise_model)
        nm.setup(self)

    def add_attacker(self, attacker):
        self.attackers.append(attacker)

    def any_attacker_found_source(self):
        return self.attacker_found_source


class OfflineSimulation(object):
    def __init__(self, module_name, configuration, args, event_log):
        self.module_name = module_name
        self.args = args

        self.seed = args.seed
        self.rng = random.Random(self.seed)

        self.nodes = []

        self._create_nodes(configuration.topology.nodes)

        if hasattr(args, "safety_period"):
            self.safety_period = args.safety_period
            
        elif hasattr(args, "source_period"):
            try:
                slowest = args.source_period.slowest()
            except AttributeError:
                slowest = float(args.source_period)

            # To make simulations safer an upper bound on the simulation time
            # is used when no safety period makes sense. This upper bound is the
            # time it would have otherwise taken the attacker to scan the whole network.
            self.safety_period = len(configuration.topology.nodes) * 2.0 * slowest

        else:
            self.safety_period = None

        self.safety_factor = getattr(args, "safety_factor", 1.0)

        self.safety_period_value = float('inf') if self.safety_period is None else (self.safety_period * self.safety_factor)

        self._line_handlers = {}

        self._callbacks = []

        self.fault_model = args.fault_model

        self.attackers = []

        self.configuration = configuration

        metrics_class = MetricsCommon.import_algorithm_metrics(module_name, args.sim, args.extra_metrics)

        # Allow flexibility with some missing metric values
        non_strict_metrics = getattr(args, "non_strict", False)

        self.metrics = metrics_class(self, configuration, strict=not non_strict_metrics)

        # Record the current user's time this script started executing at
        self.start_time = None
        self.enter_start_time = None

        # The times that the actual execution started and ended.
        # They are used to emulate sim_time and calculate the execution length.
        self._real_start_time = None
        self._real_end_time = None
        self._duration_start_time = None

        self.attacker_found_source = False

        self._event_log = event_log

        if args.mode == "GUI" or args.verbose:
            self.register_output_handler("stdout", self._stdout_printer)
        else:
            self.register_output_handler("stdout", None)

        self.debug = getattr(args, "debug", False)
        self.show_raw_log = getattr(args, "show_raw_log", False)

        import re
        self.LINE_RE = re.compile(r'([a-zA-Z-]+):([DE]):(\d+|None):(\d+|None):(.*)\s*')

    def __enter__(self):

        self.fault_model.setup(self)

        self.enter_start_time = timeit.default_timer()

        # Hide warnings about gui events, when not running in GUI mode
        if not hasattr(self, "gui"):
            self.register_output_handler("G-NC", None)
            self.register_output_handler("LedsC", None)

        return self

    def __exit__(self, tp, value, tb):
        self.metrics.finish()

    def register_output_handler(self, name, function):
        if name not in self._line_handlers:
            self._line_handlers[name] = []

        if function is not None:
            self._line_handlers[name].append(function)

    def node_distance_meters(self, left, right):
        """Get the euclidean distance between two nodes specified by their ids"""
        return self.configuration.node_distance_meters(left, right)

    def sim_time(self):
        """Returns the current simulation time in seconds"""
        try:
            return (self._real_end_time - self._real_start_time).total_seconds()
        except TypeError:
            return None

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

        raise RuntimeError(f"Unable to find a node with ordered_nid of {ordered_nid}")

    def node_from_topology_nid(self, topology_nid):
        ordered_nid = self.configuration.topology.t2o(topology_nid)

        for node in self.nodes:
            if node.nid == ordered_nid:
                return node

        raise RuntimeError(f"Unable to find a node with topology_nid of {topology_nid}")

    def _pre_run(self):
        """Called before the simulator run loop starts"""
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

    def _parse_line(self, line):
        # Example line:
        #2016/07/27 14:47:34.418:Metric-COMM:2:D:42202:DELIVER:Normal,4,1,1,22

        date_string, rest = line.split("|", 1)

        current_time = datetime.strptime(date_string, "%Y/%m/%d %H:%M:%S.%f") if date_string != "None" else None

        match = self.LINE_RE.match(rest)
        if match is not None:
            (kind, log_type, node_id, node_local_time, message_line) = match.groups()

            node_id = ast.literal_eval(node_id)
            node_local_time = ast.literal_eval(node_local_time)

            if self.args.show_raw_log:
                print(line)

            return (current_time, kind, node_local_time, log_type, node_id, message_line)
        else:
            return None

    def trigger_duration_run_start(self, time):
        if self._duration_start_time is None:
            self._duration_start_time = time

    def run(self):
        """Run the simulator loop."""

        handler_missing = object()

        log_file = open("output.log", "w") if self.debug else None

        event_count = 0
        try:
            self._pre_run()

            for line in self._event_log:

                if self.debug:
                    print(line, file=log_file)

                result = self._parse_line(line)

                if result is None:
                    hex_line = ":".join(f"{ord(c):02x}" for c in line)
                    print(f"Warning unable to parse: '{line}'. As hex: '{hex_line}'. Skipping that line.", file=sys.stderr)
                    continue

                (current_time, kind, node_local_time, log_type, node_id, message_line) = result

                # Record the start and stop time
                if self._real_start_time is None and current_time is not None:
                    self._real_start_time = current_time

                if current_time is not None:
                    self._real_end_time = current_time

                # Run any callbacks that happened before now
                while len(self._callbacks) > 0:

                    (call_at_time, callback) = self._callbacks[0]

                    if call_at_time >= self.sim_time():
                        break

                    heapq.heappop(self._callbacks)

                    callback(call_at_time)

                # Handle the event
                handlers = self._line_handlers.get(kind, handler_missing)
                if handlers is not handler_missing:
                    for handler in handlers:
                        handler(log_type, node_id, self.sim_time(), message_line)
                else:
                    print(f"There is no handler for the kind {kind}. Unable to process the line '{message_line}'.", file=sys.stderr)

                if log_type == "E":
                    print(f"An error occurred on node {node_id} at {self.sim_time()}: '{message_line}'.", file=sys.stderr)

                event_count += 1

                if hasattr(self, "_during_run"):
                    self._during_run(event_count)

                # Stop the run if the attacker has found the source
                if not self.continue_predicate():
                    break

                # Stop if the safety period has expired
                if self._duration_start_time is not None and current_time is not None:
                    if (self.sim_time() - self._duration_start_time) >= self.safety_period_value:
                        break

        finally:
            self._post_run(event_count)

            if log_file is not None:
                log_file.close()

    def _stdout_printer(self, log_type, node_id, sim_time, message):
        print(f"{sim_time} @ {node_id} : {message}")

    def add_attacker(self, attacker):
        self.attackers.append(attacker)

    def any_attacker_found_source(self):
        return self.attacker_found_source
