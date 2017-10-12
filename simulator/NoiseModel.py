
from itertools import islice
import os.path

from data.restricted_eval import restricted_eval

class NoiseModel(object):
    def setup(self, sim):
        raise NotImplementedError()

class FileTraceNoiseModel(NoiseModel):
    def __init__(self, log_file, count=2500):
        super(FileTraceNoiseModel, self).__init__()

        self.log_file = log_file
        self.count = count

        if not os.path.exists(self.log_file):
            # TODO: FileNotFoundError in Python 3
            raise RuntimeError("File not found {}".format(self.log_file))

    def setup(self, sim):
        noises = list(islice(self._read_noise_from_file(), self.count))

        for node in sim.nodes:
            tnode = node.tossim_node

            tnode.addNoiseTraces(noises)

            tnode.createNoiseModel()

    def _read_noise_from_file(self):
        with open(self.log_file, "r") as f:
            for line in f:
                if len(line) > 0 and not line.isspace():
                    yield int(line)

class TestbedTraceNoiseModel(NoiseModel):
    def __init__(self, testbed_name, log_file, count=2500):
        super(TestbedTraceNoiseModel, self).__init__()
        
        self.testbed_name = testbed_name
        self.log_file = os.path.join("testbed_results", testbed_name, "profile", log_file + "_rssi.txt")
        self.count = count

        if not os.path.exists(self.log_file):
            # TODO: FileNotFoundError in Python 3
            raise RuntimeError("File not found {}".format(self.log_file))

    def setup(self, sim):
        noises = self._read_enough_for_each_node(sim.nodes)

        for node in sim.nodes:
            tnode = node.tossim_node

            tnode.addNoiseTraces(noises[node.nid])

            tnode.createNoiseModel()

    def _read_noise_from_file(self):
        with open(self.log_file, "r") as f:
            for line in f:
                if len(line) > 0 and not line.isspace():
                    nid, rssi = line.split(",")
                    yield int(nid), int(rssi)

    def _read_enough_for_each_node(self, nodes):
        noises = {node.nid: list() for node in nodes}

        enough = set()

        for (nid, rssi) in self._read_noise_from_file():
            if nid not in noises:
                continue

            if len(noises[nid]) < self.count:
                noises[nid].append(rssi)

                if len(noises[nid]) == self.count:
                    enough.add(nid)

                    if enough == set(noises.keys()):
                        break
        else:
            missing = {nid: self.count - len(noise) for (nid, noise) in noises.items() if nid not in enough}
            raise RuntimeError("Not enough noise readings for all nodes (missing: {})".format(missing))

        return noises

# Backwards compatibility:
# These are the mappings of the old names used to refer to the models
MODEL_NAME_MAPPING = {
    "meyer-heavy": FileTraceNoiseModel("models/noise/meyer-heavy.txt", count=2500),
    "casino-lab": FileTraceNoiseModel("models/noise/casino-lab.txt", count=2500),
    "ttx4-demo": FileTraceNoiseModel("models/noise/ttx4-demo.txt", count=2500),
}

def models():
    """A list of the names of the available noise models."""
    return [subcls for subcls in NoiseModel.__subclasses__()]  # pylint: disable=no-member

def eval_input(source):
    if source in MODEL_NAME_MAPPING:
        return MODEL_NAME_MAPPING[source]

    result = restricted_eval(source, models())

    if isinstance(result, NoiseModel):
        return result
    else:
        raise RuntimeError("The source ({}) is not valid.".format(source))

def available_models():
    class WildcardModelChoice(object):
        """A special available model that checks if the string provided
        matches the name of the class.

        >> a = TestbedTraceNoiseModel("FlockLab", "41042")
        >> a == "TestbedTraceNoiseModel"
        True
        """
        def __init__(self, cls):
            self.cls = cls

        def __eq__(self, value):
            return value.startswith(self.cls.__name__)

        def __repr__(self):
            return self.cls.__name__ + "(...)"

    class_models = [WildcardModelChoice(x) for x in models()]

    return list(MODEL_NAME_MAPPING.keys()) + class_models
