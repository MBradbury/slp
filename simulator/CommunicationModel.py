from __future__ import division

from itertools import combinations
from math import log10, sqrt

import numpy as np

# Use our custom fast euclidean function,
# fallback to the slow scipy version.
try:
    from euclidean import euclidean2_2d
except ImportError:
    from scipy.spatial.distance import euclidean as euclidean2_2d

from data.restricted_eval import restricted_eval

class CommunicationModel(object):
    def __init__(self):
        self.noise_floor = None
        self.link_gain = None
        self.white_gausian_noise = None

    def setup(self, sim):
        """Set up the communication model, using parameters from the provided simulation."""
        raise NotImplementedError()

class LinkLayerCommunicationModel(CommunicationModel):
    def __init__(self, path_loss_exponent, shadowing_stddev, d0, pl_d0, noise_floor, s, white_gausian_noise):
        super(LinkLayerCommunicationModel, self).__init__()

        # Argument validity checking
        if s[0,1] != s[1,0]:
            raise RuntimeError("S12 and S21 must have the same value.")

        if abs(s[0,1]) > sqrt(s[0,0] * s[1,1]):
            raise RuntimeError("S12 (and S21) must be less than sqrt(S11xS22).")

        if s[0,0] == 0 and s[1,1] != 0:
            raise RuntimeError("Symmetric links require both, S11 and S22 to be 0, not only S11.")

        # Assign parameters
        self.path_loss_exponent = path_loss_exponent
        self.shadowing_stddev = shadowing_stddev
        self.d0 = d0
        self.pl_d0 = pl_d0
        self.noise_floor_pn = noise_floor
        self.s = s
        self.white_gausian_noise = white_gausian_noise

        self.output_power_var = None

    def setup(self, sim):
        nodes = sim.metrics.configuration.topology.nodes.values()
        rng = sim.rng

        self._setup(nodes, rng)

    def _setup(self, nodes, rng):
        """Provide a second setup function to help test this model against the Java version"""
        if __debug__:
            self._check_nodes(nodes)

        num_nodes = len(nodes)

        self.noise_floor = np.zeros(num_nodes, dtype=np.float64)
        self.output_power_var = np.zeros(num_nodes, dtype=np.float64)
        self.link_gain = np.zeros((num_nodes, num_nodes), dtype=np.float64)

        self._obtain_radio_pt_pn(nodes, rng)

        self._obtain_link_gain(nodes, rng)

    def _check_nodes(self, nodes):
        """Check that all nodes are at least d0 distance away from each other.
        This model does not work correctly when nodes are closer than d0."""

        for ((i, ni), (j, nj)) in combinations(enumerate(nodes), 2):
            distance = euclidean2_2d(ni, nj)
            if distance < self.d0:
                raise RuntimeError("The distance ({}) between any two nodes ({}={}, {}={}) must be at least d0 ({})".format(
                    distance, i, ni, j, nj, self.d0))

    def _obtain_radio_pt_pn(self, nodes, rng):

        s = self.s
        t = np.zeros((2, 2), dtype=np.float64)

        if s[0,0] == 0 and s[1,1] == 0:
            pass

        else:
            t00 = sqrt(s[0,0])

            t[0,0] = t00
            t[0,1] = s[0,1] / t00
            t[1,0] = 0.0
            t[1,1] = sqrt((s[0,0] * s[1,1] - s[0,1] * s[0,1]) / s[0,0])

        rg = rng.gauss

        for (i, ni) in enumerate(nodes):
            rnd1 = rg(0, 1)
            rnd2 = rg(0, 1)

            self.noise_floor[i] = self.noise_floor_pn + t[0,0] * rnd1
            self.output_power_var[i] = t[0,1] * rnd1 + t[1,1] * rnd2

    def _obtain_link_gain(self, nodes, rng):
        rg = rng.gauss
        ple10 = self.path_loss_exponent * 10.0
        ssd = self.shadowing_stddev
        npld0 = -self.pl_d0
        d0 = self.d0
        opv = self.output_power_var
        lg = self.link_gain

        for ((i, ni), (j, nj)) in combinations(enumerate(nodes), 2):
            rnd1 = rg(0, 1)

            distance = euclidean2_2d(ni, nj)

            pathloss = npld0 - ple10 * log10(distance / d0) + rnd1 * ssd

            lg[i,j] = opv[i] + pathloss
            lg[j,i] = opv[j] + pathloss



class IdealCommunicationModel(CommunicationModel):
    def __init__(self, connection_strength, noise_floor_pn, white_gausian_noise):
        super(IdealCommunicationModel, self).__init__()

        self.connection_strength = connection_strength
        self.noise_floor_pn = noise_floor_pn
        self.white_gausian_noise = white_gausian_noise

    def setup(self, sim):
        nodes = sim.metrics.configuration.topology.nodes.values()

        num_nodes = len(nodes)

        # All nodes have the same noise floor
        self.noise_floor = np.full(num_nodes, self.noise_floor_pn, dtype=np.float64)

        self.link_gain = np.zeros((num_nodes, num_nodes), dtype=np.float64)

        self._obtain_link_gain(nodes, sim.wireless_range)

    def _obtain_link_gain(self, nodes, wireless_range):
        lg = self.link_gain

        for ((i, ni), (j, nj)) in combinations(enumerate(nodes), 2):
            if euclidean2_2d(ni, nj) <= wireless_range:
                lg[i,j] = self.connection_strength
                lg[j,i] = self.connection_strength
            else:
                # Use NaNs to signal that there is no link between these two nodes
                lg[i,j] = float('NaN')
                lg[j,i] = float('NaN')



class LowAsymmetry(LinkLayerCommunicationModel):
    def __init__(self):
        super(LowAsymmetry, self).__init__(
            path_loss_exponent=4.7,
            shadowing_stddev=3.2,
            d0=1.0,
            pl_d0=55.4,
            noise_floor=-105.0,
            s=np.matrix(((0.9, -0.7),(-0.7, 1.2)), dtype=np.float64),
            white_gausian_noise=4.0
        )

class HighAsymmetry(LinkLayerCommunicationModel):
    def __init__(self):
        super(HighAsymmetry, self).__init__(
            path_loss_exponent=4.7,
            shadowing_stddev=3.2,
            d0=1.0,
            pl_d0=55.4,
            noise_floor=-105.0,
            s=np.matrix(((3.7, -3.3),(-3.3, 6.0)), dtype=np.float64),
            white_gausian_noise=4.0
        )

class NoAsymmetry(LinkLayerCommunicationModel):
    def __init__(self):
        super(NoAsymmetry, self).__init__(
            path_loss_exponent=4.7,
            shadowing_stddev=3.2,
            d0=1.0,
            pl_d0=55.4,
            noise_floor=-105.0,
            s=np.zeros((2, 2), dtype=np.float64),
            white_gausian_noise=4.0
        )

class Ideal(IdealCommunicationModel):
    """Perfect receive signal strength for all nodes within range."""
    def __init__(self):
        super(Ideal, self).__init__(
            connection_strength=-55,
            noise_floor_pn=-105.0,
            white_gausian_noise=4.0
        )

# Backwards compatibility:
# These are the mappings of the old names used to refer to the models
MODEL_NAME_MAPPING = {
    "low-asymmetry": LowAsymmetry,
    "high-asymmetry": HighAsymmetry,
    "no-asymmetry": NoAsymmetry,
    "ideal": Ideal,
}

def models():
    """A list of the names of the available communication models."""
    return [subsubcls
            for subcls in CommunicationModel.__subclasses__()  # pylint: disable=no-member
            for subsubcls in subcls.__subclasses__()]  # pylint: disable=no-member

def eval_input(source):
    if source in MODEL_NAME_MAPPING:
        return MODEL_NAME_MAPPING[source]

    result = restricted_eval(source, models())

    if isinstance(result, CommunicationModel):
        return result
    else:
        raise RuntimeError("The source ({}) is not valid.".format(source))
