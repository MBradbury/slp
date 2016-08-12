
import numpy as np

from simulator.Topology import Topology

def name():
    return __name__

def platform():
    """The hardware platform of the testbed"""
    return "telosb"

def log_mode():
    return "printf"

class DCSWarwick(Topology):
    """The layout of the nodes in DCS Warwick."""
    def __init__(self, initial_position=10.0):
        super(DCSWarwick, self).__init__()

        floor_distance = 20.0

        self.nodes = [
            np.array((-100, -100), dtype=np.float64),  # Padding Node - There is no node 0 in this network

            np.array((floor_distance * 2 + 0, 0),   dtype=np.float64),  # CS2.01
            np.array((floor_distance * 2 + 5, 7),   dtype=np.float64),  # CS2.08 (window)
            np.array((floor_distance * 2 + 5, 10),  dtype=np.float64),  # CS2.08 (shelf)
            np.array((floor_distance * 2 + 5, 5),   dtype=np.float64),  # CS2.06

            np.array((-100, -100), dtype=np.float64),  # Padding Node - There is no node 5 in this network

            np.array((floor_distance * 1 + 5, 5), dtype=np.float64),  # CS1.02 (far end)
            np.array((floor_distance * 1 + 5, 10), dtype=np.float64),  # CS1.02 (door)
            np.array((floor_distance * 2 + 5, 0),   dtype=np.float64),  # CS2.02

            #np.array((-1, -1), dtype=np.float64),  # Padding Node
            #np.array((-1, -1), dtype=np.float64),  # Padding Node
        ]

        # Apply the initial position
        for node in self.nodes:
            node += initial_position

    def __str__(self):
        return "DCSWarwick<>"
