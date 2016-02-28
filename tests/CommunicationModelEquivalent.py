import unittest

import subprocess, StringIO
import numpy as np

import simulator.CommunicationModel as CM
from simulator.Configuration import Configuration
from simulator.Simulation import Simulation

def communications_model_path(self, communication_model):
    return os.path.join('models', 'communication', communication_model + '.txt')

def run_link_layer_model_java(communication_model, topology_path, seed):
    output = subprocess.check_output(
        "java -Xms256m -Xmx512m -cp ./tinyos/support/sdk/java/net/tinyos/sim LinkLayerModel {} {} {}".format(
            communications_model_path(communication_model), topology_path, seed),
        shell=True)

    return sorted([line.strip() for line in output.split("\n")])

def communication_model_to_file_format(communication_model):
    output = []

    for ((i, j), gain) in np.ndenumerate(cm.link_gain):
        if i == j:
            continue
        output.append("gain\t{}\t{}\t{:.2f}".format(i, j, gain))

    for (i, noise_floor) in enumerate(cm.noise_floor):
        output.append("noise\t{}\t{:.2f}\t{:.2f}".format(i, noise_floor, awgn))

    return sorted(output)

class TestCommunicationModelEquivalent(unittest.TestCase):

    def test_equivalent_low_asymmetry(self):
        configuration = Configuration.create_specific('SourceCorner', 11, 4.5)

        seed = 44

        Simulation.write_topology_file(configuration.topology.nodes, "tests")

        cm = CM.LowAsymmetry()
        cm.setup(configuration.topology, seed)

        llm_out = run_link_layer_model_java("low-asymmetry", "tests/topology.txt", seed)
        cm_out = communication_model_to_file_format(cm)

        self.assertEqual(llm_out, cm_out)

if name == "__main__":
    unittest.main()
