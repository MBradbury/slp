from __future__ import print_function, division

from collections import namedtuple
import glob
import importlib
from itertools import islice
import os
import random
import select
import struct
import sys
import timeit

from simulator.Topology import topology_path

Node = namedtuple('Node', ('nid', 'location', 'tossim_node'), verbose=False)

class OutputCatcher(object):
    def __init__(self, linefn):
        (read, write) = os.pipe()
        self._read = os.fdopen(read, 'r')
        self._write = os.fdopen(write, 'w')
        self._linefn = linefn

    def register(self, sim, name):
        """Registers this class to catch the output from the simulation on the given channel."""
        sim.tossim.addChannel(name, self._write)

    def process_one_line(self):
        self._linefn(self._read.readline())

    def close(self):
        """Closes the file handles opened."""

        if self._read is not None:
            self._read.close()

        if self._write is not None:
            self._write.close()

        self._read = None
        self._write = None

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

        self._out_procs = {}
        self._read_poller = select.epoll()

        # Record the seed we are using
        self.seed = args.seed if args.seed is not None else self._secure_random()

        # Set tossim seed
        self.tossim.randomSeed(self.seed)

        # It is important to seed python's random number generator
        # as well as TOSSIM's. If this is not done then the simulations
        # will differ when the seeds are the same.
        random.seed(self.seed)

        self.communication_model = args.communication_model
        self.noise_model = args.noise_model
        self.wireless_range = args.distance
        self.latest_node_start_time = args.latest_node_start_time

        # Cache the number of ticks per second.
        # This value should not change throughout the simulation's execution
        self._ticks_per_second = self.tossim.ticksPerSecond()

        self._create_nodes(configuration.topology.nodes)

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

        self.topology_path = topology_path(module_name, args)

        self.start_time = None

        self.attacker_found_source = False

    def __enter__(self):
        return self

    def __exit__(self, tp, value, tb):
        del self._read_poller

        for op in self._out_procs.values():
            op.close()

        del self.nodes
        del self.radio
        del self.tossim

    def add_output_processor(self, op):
        fd = op._read.fileno()

        self._out_procs[fd] = op

        self._read_poller.register(fd, select.EPOLLIN | select.EPOLLPRI | select.EPOLLHUP | select.EPOLLERR)

    def node_distance_meters(self, left, right):
        """Get the euclidean distance between two nodes specified by their ids"""
        return self.metrics.configuration.node_distance_meters(left, right)

    def ticks_to_seconds(self, ticks):
        """Converts simulation time ticks into seconds"""
        return ticks / self._ticks_per_second

    def sim_time(self):
        """Returns the current simulation time in seconds"""
        return self.tossim.timeInSeconds()

    def _create_nodes(self, node_locations):
        """Creates nodes and initialize their boot times"""

        self.nodes = []
        for (i, loc) in enumerate(node_locations):
            tossim_node = self.tossim.getNode(i)
            new_node = Node(i, loc, tossim_node)
            self.nodes.append(new_node)

            self.set_boot_time(new_node)

    def _pre_run(self):
        """Called before the simulator run loop starts"""
        self.setup_radio()
        self.setup_noise_models()

        self.start_time = timeit.default_timer()

    def _during_run(self, event_count):
        """Called after every simulation event is executed, if some log output has been written."""

        # Query to see if there is any debug output we need to catch.
        # If there is then make the relevant OutputProcessor handle it.
        while True:
            result = self._read_poller.poll(0)

            if len(result) >= 1:
                for (fd, event) in result:
                    self._out_procs[fd].process_one_line()
            else:
                break

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

    def run(self):
        """Run the simulator loop."""
        event_count = 0
        try:
            self._pre_run()

            event_count = self.tossim.runAllEventsWithMaxTime(
                self.safety_period_value, self.continue_predicate, self._during_run)
        finally:
            self._post_run(event_count)

    def set_boot_time(self, node):
        """
        Sets the boot time of the given node to be at a
        random time between 0 and self.latest_node_start_time seconds.
        """
        start_time = int(random.uniform(0, self.latest_node_start_time) * self._ticks_per_second)
        node.tossim_node.bootAtTime(start_time)

    @staticmethod
    def write_topology_file(node_locations, location="."):
        with open(os.path.join(location, "topology.txt"), "w") as of:
            for (nid, (x, y)) in enumerate(node_locations):
                print("{}\t{}\t{}".format(nid, x, y), file=of)

    def _setup_radio_link_layer_model_java(self):
        import subprocess
        output = subprocess.check_output(
            "java -Xms256m -Xmx512m -cp ./tinyos/support/sdk/java/net/tinyos/sim LinkLayerModel {} {} {}".format(
                self.communications_model_path(), self.topology_path, self.seed),
            shell=True)

        for line in output.splitlines():
            parts = line.strip().split("\t")

            if parts[0] == "gain":
                (g, from_node_id, to_node_id, gain) = parts

                self.radio.add(int(from_node_id), int(to_node_id), float(gain))

            elif parts[0] == "noise":
                (n, node_id, noise_floor, awgn) = parts

                self.radio.setNoise(int(node_id), float(noise_floor), float(awgn))
    
    def _setup_radio_link_layer_model_python(self):
        """The python port of the java LinkLayerModel"""
        import simulator.CommunicationModel as CommunicationModel
        import numpy as np

        model = CommunicationModel.eval_input(self.communication_model)

        cm = model()
        cm.setup(self)

        for ((i, j), gain) in np.ndenumerate(cm.link_gain):
            if i == j:
                continue
            if np.isnan(gain):
                continue

            self.radio.add(i, j, gain)

        for (i, noise_floor) in enumerate(cm.noise_floor):
            self.radio.setNoise(i, noise_floor, cm.white_gausian_noise)

    def setup_radio(self):
        """Creates radio links for node pairs that are in range."""
        # Try to use the python implementation, if the java_random module
        # cannot be found then revert back to using the Java implementation.
        try:
            self._setup_radio_link_layer_model_python()
        except ImportError:
            self._setup_radio_link_layer_model_java()

    def setup_noise_models(self):
        """Create the noise model for each of the nodes in the network."""
        path = self.noise_model_path()

        # Instead of reading in all the noise data, a limited amount
        # is used. If we were to use it all it leads to large slowdowns.
        count = 1000

        noises = list(islice(self._read_noise_from_file(path), count))

        for node in self.nodes:
            for noise in noises:
                node.tossim_node.addNoiseTraceReading(noise)
            node.tossim_node.createNoiseModel()

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

    def communications_model_path(self):
        """The path to the communications model, specified in the algorithm arguments."""
        return os.path.join('models', 'communication', self.communication_model + '.txt')

    def noise_model_path(self):
        """The path to the noise model, specified in the algorithm arguments."""
        return os.path.join('models', 'noise', self.noise_model + '.txt')

    @staticmethod
    def available_noise_models():
        """Gets the names of the noise models available in the noise directory"""
        return [
            os.path.splitext(os.path.basename(noise_file))[0]
            for noise_file
            in glob.glob('models/noise/*.txt')
        ]

    @staticmethod
    def available_communication_models():
        """Gets the names of the communication models available in the models directory"""
        return [
            os.path.splitext(os.path.basename(model_file))[0]
            for model_file
            in glob.glob('models/communication/*.txt')
        ] + ["ideal"]

    @staticmethod
    def _secure_random():
        return struct.unpack("<i", os.urandom(4))[0]
