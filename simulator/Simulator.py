from __future__ import print_function, division
import os, select, random, importlib, glob

from scipy.spatial.distance import euclidean

class Node(object):
    def __init__(self, node_id, location, tossim_node):
        self.nid = node_id
        self.location = location
        self.tossim_node = tossim_node

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

class Simulator(object):
    def __init__(self, module_name, node_locations, wireless_range, latest_node_start_time, seed, load_nesc_variables=False):
        super(Simulator, self).__init__()

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

        self.out_procs = {}
        self.nodes = []

        # Set tossim seed
        self.tossim.randomSeed(seed)

        # Record the seed we are using
        self.seed = seed

        # It is important to seed python's random number generator
        # as well as TOSSIM's. If this is not done then the simulations
        # will differ when the seeds are the same.
        random.seed(self.seed)

        self.range = wireless_range

        self.create_nodes(node_locations)

        # Randomly set the boot times for all nodes
        self.latest_node_start_time = latest_node_start_time
        for n in self.nodes:
            self.set_boot_time(n)

        self._read_poller = select.poll()
        

    def __enter__(self):
        return self

    def __exit__(self, tp, value, tb):
        del self._read_poller

        for op in self.out_procs.values():
            op.close()

        del self.nodes
        del self.radio
        del self.tossim

    def add_output_processor(self, op):
        fd = op._read.fileno()

        self.out_procs[fd] = op

        self._read_poller.register(fd, select.POLLIN | select.POLLPRI | select.POLLHUP | select.POLLERR)

    def node_distance(self, left, right):
        """Get the euclidean distance between two nodes specified by their ids"""
        return euclidean(self.nodes[left].location, self.nodes[right].location)

    def ticks_to_seconds(self, ticks):
        """Converts simulation time ticks into seconds"""
        return float(ticks) / self.tossim.ticksPerSecond()

    def sim_time(self):
        """Returns the current simulation time in seconds"""
        return float(self.tossim.time()) / self.tossim.ticksPerSecond()

    def create_nodes(self, node_locations):
        """Creates nodes and initialize their boot times"""

        self.nodes = []
        for (i, loc) in enumerate(node_locations):
            tossim_node = self.tossim.getNode(i)
            new_node = Node(i, loc, tossim_node)
            self.nodes.append(new_node)

    def setup_noise_models(self):
        """Create the noise model for each of the nodes in the network."""
        raise NotImplementedError()

    def setup_radio(self):
        """Creates radio links for node pairs that are in range."""
        raise NotImplementedError()

    @staticmethod
    def read_noise_from_file(path):
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if len(line) != 0:
                    yield int(line)

    def set_boot_time(self, node):
        """
        Sets the boot time of the given node to be at a
        random time between 0 and self.latest_node_start_time seconds.
        """
        start_time = int(random.uniform(0, self.latest_node_start_time) * self.tossim.ticksPerSecond())
        node.tossim_node.bootAtTime(start_time)

    def move_node(self, node, location, time=None):
        '''
        Schedules the specified node to move to the new location at the
        specified time.  If time is omitted, move the node immediately.
        '''
        # This function requires access to the simulation queue.  TOSSIM must be
        # patched for it to work
        raise NotImplementedError("Need TOSSIM patching")

    def continue_predicate(self):
        """Specifies if the simulator run loop should continue executing."""
        return True

    def _pre_run(self):
        """Called before the simulator run loop starts"""
        self.setup_radio()
        self.setup_noise_models()

    def _post_run(self, event_count):
        """Called after the simulator run loop finishes"""
        pass

    def _during_run(self, event_count):
        """Called after every simulation event is executed"""

        # Query to see if there is any debug output we need to catch.
        # If there is then make the relevant OutputProcessor handle it.
        while True:
            result = self._read_poller.poll(0)

            if len(result) >= 1:
                for (fd, event) in result:
                    self.out_procs[fd].process_one_line()
            else:
                break

    def run(self):
        """Run the simulator loop."""
        event_count = 0
        try:
            self._pre_run()

            event_count = self.tossim.runAllEvents(self.continue_predicate, self._during_run)
        finally:
            self._post_run(event_count)

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
