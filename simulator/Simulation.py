from __future__ import print_function
import os, timeit, struct, importlib, subprocess, sys

from itertools import islice

from simulator.Simulator import Simulator
from simulator.Topology import topology_path

from scipy.spatial.distance import euclidean

class Simulation(Simulator):
    def __init__(self, module_name, configuration, args, load_nesc_variables=False):

        super(Simulation, self).__init__(
            module_name=module_name,
            node_locations=configuration.topology.nodes,
            wireless_range=args.distance,
            latest_node_start_time=args.latest_node_start_time,
            seed=args.seed if args.seed is not None else self._secure_random(),
            load_nesc_variables=load_nesc_variables
            )

        if hasattr(args, "safety_period"):
            self.safety_period = args.safety_period
        else:
            # To make simulations safer an upper bound on the simulation time
            # is used when no safety period makes sense. This upper bound is the
            # time it would have otherwise taken the attacker to scan the whole network.
            self.safety_period = len(configuration.topology.nodes) * 2.0 * args.source_period.slowest()

        if args.mode == "GUI" or args.verbose:
            self.tossim.addChannel("stdout", sys.stdout)
            self.tossim.addChannel("stderr", sys.stderr)
            self.tossim.addChannel("slp-debug", sys.stdout)

        self.communication_model = args.communication_model
        self.noise_model = args.noise_model

        self.attackers = []

        metrics_module = importlib.import_module('{}.Metrics'.format(module_name))

        self.metrics = metrics_module.Metrics(self, configuration)

        self.topology_path = topology_path(module_name, args)

        self.start_time = None

        self.attacker_found_source = False

    def communications_model_path(self):
        """The path to the communications model, specified in the algorithm arguments."""
        return os.path.join('models', 'communication', self.communication_model + '.txt')

    def noise_model_path(self):
        """The path to the noise model, specified in the algorithm arguments."""
        return os.path.join('models', 'noise', self.noise_model + '.txt')

    def _pre_run(self):
        super(Simulation, self)._pre_run()

        self.start_time = timeit.default_timer()

    def _post_run(self, event_count):

        # Set the number of seconds this simulation run took.
        # It is possible that we will reach here without setting
        # start_time, so we need to look out for this.
        try:
            self.metrics.wall_time = timeit.default_timer() - self.start_time
        except TypeError:
            self.metrics.wall_time = None

        self.metrics.event_count = event_count

        super(Simulation, self)._post_run(event_count)

    @staticmethod
    def write_topology_file(node_locations, location="."):
        with open(os.path.join(location, "topology.txt"), "w") as of:
            for (nid, loc) in enumerate(node_locations):
                print("{}\t{}\t{}".format(nid, loc[0], loc[1]), file=of)

    def _setup_radio_link_layer_model(self):
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

    def _setup_radio_ideal(self):
        '''Creates radio links for node pairs that are in range'''

        def compute_rf_gain(src, dst):
            '''
            Returns signal reception gain between src and dst using a simple
            range-threshold model.
            '''
            if src != dst and euclidean(src.location, dst.location) <= self.range:
                return (True, -55)
            else:
                return (False, None)

        noise_floor = -105.0
        white_gaussian_noise = 4.0

        num_nodes = len(self.nodes)
        for (i, ni) in enumerate(self.nodes):
            for (j, nj) in enumerate(self.nodes):
                if i != j:
                    (is_linked, gain) = compute_rf_gain(ni, nj)
                    if is_linked:
                        self.radio.add(i, j, gain)

                        #print("Added link: {} <-> {} ({})".format(i, j, gain))

            self.radio.setNoise(i, noise_floor, white_gaussian_noise)

            #print("Set Noise: {} = {} / {}".format(i, noise_floor, white_gaussian_noise))


    def setup_radio(self):
        if self.communication_model == "ideal":
            self._setup_radio_ideal()
        else:
            self._setup_radio_link_layer_model()

    def setup_noise_models(self):
        path = self.noise_model_path()

        # Instead of reading in all the noise data, a limited amount
        # is used. If we were to use it all it leads to large slowdowns.
        count = 1000

        noises = list(islice(self.read_noise_from_file(path), count))

        for node in self.nodes:
            for noise in noises:
                node.tossim_node.addNoiseTraceReading(noise)
            node.tossim_node.createNoiseModel()

    def add_attacker(self, attacker):
        self.attackers.append(attacker)

    def continue_predicate(self, time):
        # For performance reasons do not do anything expensive in this function,
        # that includes simple things such as iterating or calling functions.
        return not self.attacker_found_source and (self.safety_period is None or time < self.safety_period)

    def any_attacker_found_source(self):
        return self.attacker_found_source

    @staticmethod
    def _secure_random():
        return struct.unpack("<i", os.urandom(4))[0]
