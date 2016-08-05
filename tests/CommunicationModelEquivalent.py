from __future__ import print_function, division

import os
import unittest

import subprocess, StringIO
import numpy as np

import simulator.CommunicationModel as CM
import simulator.Configuration
from simulator.Simulation import Simulation

def communications_model_path(communication_model):
    return os.path.join('models', 'communication', communication_model + '.txt')

def run_link_layer_model_java(communication_model, topology_path, seed):
    path = communications_model_path(communication_model)

    output = subprocess.check_output(
        "java -Xms256m -Xmx512m -cp ./tinyos/support/sdk/java/net/tinyos/sim LinkLayerModel {} {} {}".format(
            path, topology_path, seed),
        shell=True)

    result = sorted([line.strip() for line in output.split("\n")])

    return result

def communication_model_to_file_format(cm):
    output = ['']

    for ((i, j), gain) in np.ndenumerate(cm.link_gain):
        if i == j:
            continue
        output.append("gain\t{}\t{}\t{:.2f}".format(i, j, gain))

    for (i, noise_floor) in enumerate(cm.noise_floor):
        output.append("noise\t{}\t{:.2f}\t{:.2f}".format(i, noise_floor, cm.white_gausian_noise))

    result = sorted(output)

    return result

class TestCommunicationModelEquivalent(unittest.TestCase):

    def test_equivalent_high_asymmetry(self):
        configuration = simulator.Configuration.create_specific('SourceCorner', 11, 4.5)

        for seed in [-109, -1, 0, 45]:
            Simulation.write_topology_file(configuration.topology.nodes, "tests")

            cm = CM.HighAsymmetry()
            cm._setup(configuration.topology, seed)

            llm_out = run_link_layer_model_java("high-asymmetry", "tests/topology.txt", seed)
            cm_out = communication_model_to_file_format(cm)

            self.assertEqual(llm_out, cm_out)

    def test_equivalent_low_asymmetry(self):
        configuration = simulator.Configuration.create_specific('SourceCorner', 11, 4.5)

        for seed in [-109, -1, 0, 45]:
            Simulation.write_topology_file(configuration.topology.nodes, "tests")

            cm = CM.LowAsymmetry()
            cm._setup(configuration.topology, seed)

            llm_out = run_link_layer_model_java("low-asymmetry", "tests/topology.txt", seed)
            cm_out = communication_model_to_file_format(cm)

            self.assertEqual(llm_out, cm_out)

    def test_equivalent_no_asymmetry(self):
        configuration = simulator.Configuration.create_specific('SourceCorner', 11, 4.5)

        for seed in [-109, -1, 0, 45]:
            Simulation.write_topology_file(configuration.topology.nodes, "tests")

            cm = CM.NoAsymmetry()
            cm._setup(configuration.topology, seed)

            llm_out = run_link_layer_model_java("no-asymmetry", "tests/topology.txt", seed)
            cm_out = communication_model_to_file_format(cm)

            self.assertEqual(len(llm_out), len(cm_out))

            for (llmo, cmo) in zip(llm_out, cm_out):
                self.assertEqual(llmo, cmo)

    def tearDown(self):
        os.remove("tests/topology.txt")

if __name__ == "__main__":
    unittest.main()
