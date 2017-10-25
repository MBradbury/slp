from __future__ import print_function, division

import itertools
import os
import unittest

import numpy as np

try:
    from euclidean import euclidean2_2d
except ImportError:
    from scipy.spatial.distance import euclidean as euclidean2_2d

import simulator.CommunicationModel as CM
import simulator.Configuration
from simulator.Topology import TopologyId

class TestConfigurationDistances(unittest.TestCase):

    def test_simple(self):
        configurationt = simulator.Configuration.create_specific('SourceCorner', 11, 4.5, "topology")
        configurationr = simulator.Configuration.create_specific('SourceCorner', 11, 4.5, "randomised")

        self.assertEqual(configurationt.sink_ids, set(map(configurationr.topology.o2t, configurationr.sink_id2)))
        self.assertEqual(configurationt.source_ids, set(map(configurationr.topology.o2t, configurationr.source_ids)))

    def test_size(self):
        sizes = [11, 15, 21, 25]
        node_id_orders = ["topology", "randomised"]

        for (size, node_id_order) in itertools.product(sizes, node_id_orders):

            configuration = simulator.Configuration.create_specific('SourceCorner', size, 4.5, node_id_order)

            self.assertEqual(configuration.size(), size*size)

    def test_ssd_topology(self):
        configuration = simulator.Configuration.create_specific('SourceCorner', 11, 4.5, "topology")
        source_id = TopologyId(0)

        self.assertIn(source_id, configuration.source_ids)
        self.assertEqual(configuration.ssd(source_id), 10)

        with self.assertRaises(RuntimeError):
            configuration.ssd(1)

    def test_ssd_randomised(self):
        configuration = simulator.Configuration.create_specific('SourceCorner', 11, 4.5, "randomised")
        source_id = TopologyId(0)
        adjusted_source_id = configuration.topology.t2o(source_id)

        self.assertIn(adjusted_source_id, configuration.source_ids)
        self.assertEqual(configuration.ssd(adjusted_source_id), 10)

        # Get another node id that is not the source
        with self.assertRaises(RuntimeError):
            configuration.ssd((adjusted_source_id + 1) % configuration.size())

    def test_node_distance(self):
        configuration = simulator.Configuration.create_specific('SourceCorner', 11, 4.5, "topology")
        from_nid = TopologyId(1)
        to_nid = TopologyId(15)
        topology_result = configuration.node_distance(from_nid, to_nid)

        expected_result = 4

        self.assertEqual(topology_result, expected_result)

        configuration = simulator.Configuration.create_specific('SourceCorner', 11, 4.5, "randomised")
        from_nid = configuration.topology.t2o(from_nid)
        to_nid = configuration.topology.t2o(to_nid)
        randomised_result = configuration.node_distance(from_nid, to_nid)

        self.assertEqual(randomised_result, expected_result)

        self.assertEqual(topology_result, randomised_result)

    def test_node_distance_meters(self):
        configuration = simulator.Configuration.create_specific('SourceCorner', 11, 4.5, "topology")
        from_nid = TopologyId(1)
        to_nid = TopologyId(15)
        topology_result = configuration.node_distance_meters(from_nid, to_nid)

        from_coords = np.array((0 * 4.5, 1 * 4.5), dtype=np.float64)
        to_coords = np.array((1 * 4.5, 4 * 4.5), dtype=np.float64)
        expected_result = euclidean2_2d(from_coords, to_coords)

        self.assertEqual(topology_result, expected_result)

        configuration = simulator.Configuration.create_specific('SourceCorner', 11, 4.5, "randomised")
        from_nid = configuration.topology.t2o(from_nid)
        to_nid = configuration.topology.t2o(to_nid)
        randomised_result = configuration.node_distance_meters(from_nid, to_nid)

        self.assertEqual(randomised_result, expected_result)

        self.assertEqual(topology_result, randomised_result)

    def test_ssd_meters(self):
        configuration = simulator.Configuration.create_specific('SourceCorner', 11, 4.5, "topology")
        source = TopologyId(0)
        topology_result = configuration.ssd_meters(source)

        from_coords = np.array((0 * 4.5, 0 * 4.5), dtype=np.float64)
        to_coords = np.array((5 * 4.5, 5 * 4.5), dtype=np.float64)
        expected_result = euclidean2_2d(from_coords, to_coords)

        self.assertEqual(topology_result, expected_result)

        configuration = simulator.Configuration.create_specific('SourceCorner', 11, 4.5, "randomised")
        source = configuration.topology.t2o(source)
        randomised_result = configuration.ssd_meters(source)

        self.assertEqual(randomised_result, expected_result)

        self.assertEqual(topology_result, randomised_result)

    def test_shortest_path(self):
        configuration = simulator.Configuration.create_specific('SourceCorner', 11, 4.5, "topology")
        from_nid = TopologyId(1)
        to_nid = TopologyId(15)
        topology_result = configuration.shortest_path(from_nid, to_nid)

        expected_result = ([1, 12, 13, 14, 15], [1, 2, 13, 14, 15], [1, 2, 3, 14, 15], [1, 2, 3, 4, 15])

        self.assertIn(topology_result, expected_result)

        configuration = simulator.Configuration.create_specific('SourceCorner', 11, 4.5, "randomised")
        from_nid = configuration.topology.t2o(from_nid)
        to_nid = configuration.topology.t2o(to_nid)
        randomised_result = configuration.shortest_path(from_nid, to_nid)

        expected_result = tuple(list(map(configuration.topology.t2o, result)) for result in expected_result)

        self.assertIn(randomised_result, expected_result)

        self.assertEqual(topology_result, map(configuration.topology.o2t, randomised_result))


if __name__ == "__main__":
    unittest.main()
