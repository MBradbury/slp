from __future__ import print_function
import os, math, select, random, gc, importlib

from tinyos.tossim.TossimApp import NescApp

from scipy.spatial.distance import euclidean

class Node(object):
    def __init__(self, node_id, location, tossim_node):
        self.nid = node_id
        self.location = location
        self.tossim_node = tossim_node

class OutputCatcher(object):
    def __init__(self, linefn):
        (read, write) = os.pipe()
        self.read = os.fdopen(read, 'r')
        self.write = os.fdopen(write, 'w')
        self.linefn = linefn

    def process(self):
        """Consumes any lines that have been caught."""
        while True:
            (read, write, error) = select.select([self.read.fileno()], [], [], 0)
            if len(read) == 1:
                line = self.read.readline()
                self.linefn(line)
            else:
                break

    def close(self):
        if self.read is not None:
            self.read.close()

        if self.write is not None:
            self.write.close()

        self.read = None
        self.write = None

class Simulator(object):
    def __init__(self, module_name, node_locations, wireless_range, seed):

        TOSSIM = importlib.import_module('{}.TOSSIM'.format(module_name))

        app_path = os.path.join('.', module_name.replace('.', os.sep), 'app.xml')

        self.nesc_app = NescApp(xmlFile=app_path)
        self.tossim = TOSSIM.Tossim(self.nesc_app.variables.variables())
        self.radio = self.tossim.radio()

        self.out_procs = []
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
        for n in self.nodes:
            self.set_boot_time(n)

    def __enter__(self):
        return self

    def __exit__(self, tp, value, tb):
        for op in self.out_procs:
            op.close()

        del self.nodes
        del self.radio
        del self.tossim

    def add_output_processor(self, op):
        self.out_procs.append(op)

    def node_distance(self, left, right):
        return euclidean(self.nodes[left].location, self.nodes[right].location)

    def sim_time(self):
        """Returns the current simulation time in seconds"""
        return float(self.tossim.time())/self.tossim.ticksPerSecond()

    def create_nodes(self, node_locations):
        """Creates nodes and initialize their boot times"""

        self.nodes = []
        for (i, loc) in enumerate(node_locations):
            tossim_node = self.tossim.getNode(i)
            new_node = Node(i, loc, tossim_node)
            self.nodes.append(new_node)

    def setup_noise_models(self):
        for node in self.nodes:
            self.create_noise_model(node)

    # DO NOT USE THIS!
    """def setup_radio(self):
        '''Creates radio links for node pairs that are in range'''
        num_nodes = len(self.nodes)
        for i, ni in enumerate(self.nodes):
            for j, nj in enumerate(self.nodes):
                if i != j:
                    (is_linked, gain) = self.compute_rf_gain(ni, nj)
                    if is_linked:
                        self.radio.add(i, j, gain)
                        #if self.drawNeighborLinks:
                        #   self.scene.execute(0, 'addlink(%d,%d,1)' % (i,j))"""

    @staticmethod
    def read_noise_from_file(path):
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if len(line) != 0:
                    yield int(line)

    # DO NOT USE THIS!
    """def create_noise_model(self, node):
        '''
        Either override this method or setup_noise_models to use a better noise model.
        For example use a noise trace file such as meyer-heavy.txt.
        '''
        for i in range(100):
            node.tossim_node.addNoiseTraceReading(int(random.random()*20)-75)
        node.tossim_node.createNoiseModel()"""

    # DO NOT USE THIS!
    """def compute_rf_gain(self, src, dst):
        '''
        Returns signal reception gain between src and dst using a simple
        range-threshold model.  Should be overridden with a more realistic
        propagation model.
        '''
        if src == dst:
            return (False, None)

        (x1, y1) = src.location
        (x2, y2) = dst.location
        dx = x1 - x2
        dy = y1 - y2
        if math.sqrt(dx*dx + dy*dy) <= self.range:
            return (True, -55)
        else:
            return (False, None)"""

    def set_boot_time(self, node):
        node.tossim_node.bootAtTime(int(random.random() * self.tossim.ticksPerSecond()))

    def move_node(self, node, location, time=None):
        '''
        Schedules the specified node to move to the new location at the
        specified time.  If time is omitted, move the node immediately.
        '''
        # This function requires access to the simulation queue.  TOSSIM must be
        # patched for it to work
        raise NotImplementedError("Need TOSSIM patching")

    def continue_predicate(self):
        return True

    def _pre_run(self):
        self.setup_radio()
        self.setup_noise_models()

    def _post_run(self, event_count):
        pass

    def _during_run(self, event_count):
        for op in self.out_procs:
            op.process()

    def run(self):
        """Run the simulator loop."""

        event_count = 0

        # Lets disable the python GC, so that it will not be run
        # in this tight loop that shouldn't allocate much memory
        try:
            gc.disable()

            self._pre_run()

            while self.continue_predicate():
                if self.tossim.runNextEvent() == 0:
                    print("Run next event returned 0 ({})".format(event_count))
                    break

                self._during_run(event_count)

                event_count += 1

        finally:
            gc.enable()

            self._post_run(event_count)
